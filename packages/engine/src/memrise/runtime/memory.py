from __future__ import annotations

import asyncio
from typing import Any

from memrise.consolidation.graph_projection import GraphProjectionService
from memrise.core.enums import (
    Criticality,
    EpisodeKind,
    FeedbackOutcome,
    FeedbackSource,
    JobStatus,
    JobType,
    MemoryType,
)
from memrise.core.graph import clamp_graph_depth
from memrise.core.models import BackgroundJob, Episode, Feedback
from memrise.core.time import utc_now
from memrise.ports.graph_repository import GraphRepository
from memrise.ports.providers import (
    CompletionProvider,
    EmbeddingProvider,
    ExtractedGraphRelation,
    ExtractedMemoryCandidate,
    TokenCounter,
)
from memrise.ports.repositories import FeedbackPolicy, JobQueue, MemoryStore
from memrise.read.explanation import ExplanationService
from memrise.read.retrieval import RetrievalService
from memrise.runtime.clock import SystemClock
from memrise.runtime.graph_responses import build_graph_neighborhood_response
from memrise.runtime.ids import UuidGenerator
from memrise.runtime.mappers import (
    retrieval_item_to_summary,
    to_job_summary,
    to_retrieved_memory,
)
from memrise.runtime.scope import scope_from_namespace_agent
from memrise.runtime.settings import MemorySettings
from memrise.schemas.mappers import memory_to_summary
from memrise.schemas.requests import (
    CaptureEvent,
    CaptureRequest,
    ConsolidateRequest,
    FeedbackRequest,
    RememberRequest,
    RetrieveRequest,
)
from memrise.schemas.responses import (
    CaptureResponse,
    ConsolidateResponse,
    FeedbackResponse,
    GraphNeighborhoodResponse,
    JobSummary,
    MemoryExplanation,
    MemorySummary,
    RememberResponse,
    RetrievalDetail,
    RetrievalTraceSummary,
    RetrieveResponse,
)
from memrise.write.importance import ImportanceGate
from memrise.write.service import WriteService


class Memrise:
    def __init__(
        self,
        *,
        store: MemoryStore,
        jobs: JobQueue,
        graph_repository: GraphRepository,
        graph_projection: GraphProjectionService,
        completion_provider: CompletionProvider,
        embedding_provider: EmbeddingProvider,
        token_counter: TokenCounter,
        feedback_policy: FeedbackPolicy,
    ) -> None:
        self._store = store
        self._jobs = jobs
        self._graph_repository = graph_repository
        self._graph_projection = graph_projection
        self._completion_provider = completion_provider
        self._embedding_provider = embedding_provider
        self._token_counter = token_counter
        self._feedback_policy = feedback_policy
        self._clock = SystemClock()
        self._ids = UuidGenerator()
        self._write = WriteService(
            store=store,
            jobs=jobs,
            completion_provider=completion_provider,
            embedding_provider=embedding_provider,
            importance_gate=ImportanceGate(),
            id_generator=self._ids,
        )
        self._retrieval = RetrievalService(
            store=store,
            graph_repository=graph_repository,
            embedding_provider=embedding_provider,
            token_counter=token_counter,
            ids=self._ids,
        )
        self._explain = ExplanationService(store, graph_repository=graph_repository)

    @classmethod
    def from_env(cls) -> Memrise:
        settings = MemorySettings()
        if settings.database_url:
            from memrise.runtime.bootstrap import build_postgres_memory

            return build_postgres_memory(settings)
        msg = "DATABASE_URL is required; Memrise no longer ships an in-memory runtime fallback"
        raise ValueError(msg)

    @property
    def store(self) -> MemoryStore:
        return self._store

    @property
    def jobs(self) -> JobQueue:
        return self._jobs

    async def capture(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        session_id: str,
        events: list[CaptureEvent | dict[str, Any]],
        user_id: str | None = None,
        project_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CaptureResponse:
        request = CaptureRequest.model_validate(
            {
                "namespace_id": namespace_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "events": events,
                "user_id": user_id,
                "project_id": project_id,
                "idempotency_key": idempotency_key,
            }
        )
        episode_ids: list[str] = []
        job_ids: list[str] = []
        for event in request.events:
            episode = Episode(
                id=self._ids.new_id("episode"),
                namespace_id=request.namespace_id,
                agent_id=request.agent_id,
                user_id=request.user_id,
                session_id=request.session_id,
                project_id=request.project_id,
                kind=event.kind,
                content=event.content,
                metadata=event.metadata,
                created_at=self._clock.now(),
                idempotency_key=request.idempotency_key,
            )
            saved_episode, job_id = await self._write.capture_episode(episode)
            episode_ids.append(saved_episode.id)
            if job_id:
                job_ids.append(job_id)
        return CaptureResponse(episode_ids=episode_ids, job_ids=job_ids)

    async def remember(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        subject: str,
        key: str,
        content: str,
        type: MemoryType,
        user_id: str | None = None,
        project_id: str | None = None,
        structured_value: dict[str, Any] | None = None,
        confidence: float = 0.9,
        importance: float = 0.7,
        criticality: Criticality = Criticality.NORMAL,
        applicability: dict[str, Any] | None = None,
        source_episode_content: str | None = None,
        source_episode_metadata: dict[str, Any] | None = None,
        graph_relations: list[tuple[str, str, str]] | None = None,
        valid_until: str | None = None,
    ) -> RememberResponse:
        request = RememberRequest.model_validate(
            {
                "namespace_id": namespace_id,
                "agent_id": agent_id,
                "subject": subject,
                "key": key,
                "content": content,
                "type": type,
                "user_id": user_id,
                "project_id": project_id,
                "structured_value": structured_value or {},
                "confidence": confidence,
                "importance": importance,
                "criticality": criticality,
                "applicability": applicability or {},
                "source_episode_content": source_episode_content,
                "source_episode_metadata": source_episode_metadata or {},
                "graph_relations": graph_relations or [],
                "valid_until": valid_until,
            }
        )
        scope = scope_from_namespace_agent(
            namespace_id=request.namespace_id,
            agent_id=request.agent_id,
            user_id=request.user_id,
            project_id=request.project_id,
        )
        source_episode_id: str | None = None
        source_episode_ids: list[str] = []
        if request.source_episode_content:
            source_episode_id = self._ids.new_id("episode")
            episode = Episode(
                id=source_episode_id,
                namespace_id=request.namespace_id,
                agent_id=request.agent_id,
                user_id=request.user_id,
                session_id=f"structured:{source_episode_id}",
                project_id=request.project_id,
                kind=EpisodeKind.ENVIRONMENT_OBSERVATION,
                content=request.source_episode_content,
                metadata=request.source_episode_metadata,
                created_at=self._clock.now(),
            )
            await self._store.save_episode(episode)
            source_episode_ids.append(source_episode_id)
        candidate = ExtractedMemoryCandidate(
            type=request.type,
            subject=request.subject,
            key=request.key,
            content=request.content,
            structured_value=request.structured_value,
            confidence=request.confidence,
            importance=request.importance,
            criticality=request.criticality,
            operation_hint=None,
            valid_until=request.valid_until,
            evidence_quote=request.source_episode_content or request.content,
            graph_relations=[
                ExtractedGraphRelation(source=source, relation=relation, target=target)
                for source, relation, target in request.graph_relations
            ],
        )
        embedding = await self._embedding_provider.embed(request.content)
        apply_outcome = await self._store.apply_candidate(
            scope=scope,
            candidate=candidate,
            source_episode_ids=source_episode_ids,
            embedding=embedding,
        )
        memory = apply_outcome.memory
        if memory is None:
            existing = await self._store.find_current_memory(
                scope=scope,
                subject=request.subject,
                key=request.key,
            )
            if existing is None:
                msg = "structured memory was rejected and no current memory exists"
                raise RuntimeError(msg)
            memory = existing
        await self._store.schedule_graph_projection(
            memory=memory, relations=candidate.graph_relations
        )
        return RememberResponse(
            memory=memory_to_summary(memory), source_episode_id=source_episode_id
        )

    async def retrieve(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        query: str,
        user_id: str | None = None,
        project_id: str | None = None,
        task_type: str | None = None,
        token_budget: int = 800,
        limit: int = 10,
        graph_hops: int = 1,
    ) -> RetrieveResponse:
        request = RetrieveRequest.model_validate(
            {
                "namespace_id": namespace_id,
                "agent_id": agent_id,
                "query": query,
                "user_id": user_id,
                "project_id": project_id,
                "task_type": task_type,
                "token_budget": token_budget,
                "limit": limit,
                "graph_hops": graph_hops,
            }
        )
        scope = scope_from_namespace_agent(
            namespace_id=request.namespace_id,
            agent_id=request.agent_id,
            user_id=request.user_id,
            project_id=request.project_id,
        )
        retrieval_id, critical, memories, context, used_tokens = await self._retrieval.retrieve(
            scope=scope,
            query=request.query,
            task_type=request.task_type,
            token_budget=request.token_budget,
            limit=request.limit,
            graph_hops=request.graph_hops,
        )
        return RetrieveResponse(
            retrieval_id=retrieval_id,
            query=request.query,
            token_budget=request.token_budget,
            used_tokens=used_tokens,
            critical=[
                await to_retrieved_memory(
                    memory=memory,
                    store=self._store,
                    token_counter=self._token_counter,
                    selected=True,
                )
                for memory in critical
            ],
            memories=[
                await to_retrieved_memory(
                    memory=memory,
                    store=self._store,
                    token_counter=self._token_counter,
                    selected=True,
                )
                for memory in memories
            ],
            context=context,
        )

    async def feedback(
        self,
        retrieval_id: str,
        *,
        outcome: FeedbackOutcome,
        source: FeedbackSource,
        memory_version_id: str | None = None,
        graph_edge_id: str | None = None,
        confidence: float | None = None,
        task_type: str | None = None,
    ) -> FeedbackResponse:
        request = FeedbackRequest.model_validate(
            {
                "outcome": outcome,
                "source": source,
                "memory_version_id": memory_version_id,
                "graph_edge_id": graph_edge_id,
                "confidence": confidence,
                "task_type": task_type,
            }
        )
        confidence = self._feedback_policy.confidence_for(request.source, request.confidence)
        feedback = Feedback(
            id=self._ids.new_id("feedback"),
            retrieval_id=retrieval_id,
            outcome=request.outcome,
            source=request.source,
            confidence=confidence,
            created_at=self._clock.now(),
            memory_version_id=request.memory_version_id,
            graph_edge_id=request.graph_edge_id,
            task_type=request.task_type,
        )
        score = await self._store.save_feedback(feedback)
        if feedback.graph_edge_id is not None and score is not None:
            await self._graph_repository.update_edge_usefulness(
                feedback.graph_edge_id,
                score,
            )
        return FeedbackResponse(
            feedback_id=feedback.id,
            updated_memory_version_id=request.memory_version_id,
            updated_graph_edge_id=request.graph_edge_id,
            usefulness_score=score,
        )

    async def consolidate(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        session_id: str,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> ConsolidateResponse:
        request = ConsolidateRequest.model_validate(
            {
                "namespace_id": namespace_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "user_id": user_id,
                "project_id": project_id,
            }
        )
        job_id = await self._jobs.enqueue(
            job_type=JobType.CONSOLIDATE_SESSION,
            payload=request.model_dump(exclude_none=True),
            dedupe_key=f"consolidate:{request.namespace_id}:{request.agent_id}:{request.session_id}",
        )
        return ConsolidateResponse(job_id=job_id, accepted=True)

    async def list_memories(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[MemorySummary]:
        memories = await self._store.list_active_memories(
            scope=scope_from_namespace_agent(
                namespace_id=namespace_id,
                agent_id=agent_id,
                user_id=user_id,
                project_id=project_id,
            ),
            user_id_is_wildcard=user_id is None,
            project_id_is_wildcard=project_id is None,
        )
        return [memory_to_summary(memory) for memory in memories]

    async def get_memory(self, memory_id: str) -> MemorySummary | None:
        explanation = await self.explain(memory_id)
        return explanation.current_version

    async def explain(self, memory_id: str) -> MemoryExplanation:
        return await self._explain.explain(memory_id)

    async def list_retrievals(
        self,
        *,
        namespace_id: str,
        limit: int = 20,
    ) -> list[RetrievalTraceSummary]:
        traces = await self._store.list_recent_retrievals(namespace_id=namespace_id, limit=limit)
        return [
            RetrievalTraceSummary(
                id=trace.id,
                namespace_id=trace.namespace_id,
                agent_id=trace.agent_id,
                query=trace.query,
                task_type=trace.task_type,
                project_id=trace.project_id,
                token_budget=trace.token_budget,
                created_at=trace.created_at,
            )
            for trace in traces
        ]

    async def get_retrieval(self, retrieval_id: str) -> RetrievalDetail:
        items = await self._store.get_retrieval_items(retrieval_id)
        return RetrievalDetail(
            retrieval_id=retrieval_id,
            items=[retrieval_item_to_summary(item) for item in items],
        )

    async def graph_neighborhood(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        query: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
        hops: int = 1,
    ) -> GraphNeighborhoodResponse:
        del agent_id, user_id
        depth = clamp_graph_depth(hops)
        paths = await self._graph_repository.get_neighborhood(
            node_uid=query or "",
            namespace_id=namespace_id,
            depth=depth,
        )
        return build_graph_neighborhood_response(paths, project_id=project_id)

    async def wait_for_job(
        self,
        job_id: str,
        *,
        timeout_seconds: float = 30.0,
        poll_seconds: float = 0.2,
    ) -> JobSummary:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            job = await self._jobs.get_job(job_id)
            if job is None:
                msg = f"job {job_id!r} not found"
                raise KeyError(msg)
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                return to_job_summary(job)
            if asyncio.get_running_loop().time() >= deadline:
                return to_job_summary(job)
            await asyncio.sleep(poll_seconds)

    async def close(self) -> None:
        return None

    async def __aenter__(self) -> Memrise:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def process_job_once(self, worker_id: str = "inline-worker") -> bool:
        job = await self._jobs.claim_next(worker_id=worker_id)
        if job is None:
            return False
        try:
            await self.process_job(job)
            await self._jobs.complete(job.id)
        except Exception as exc:
            await self._jobs.fail(job.id, str(exc))
            raise
        return True

    async def process_job(self, job: BackgroundJob) -> None:
        if job.type == JobType.EXTRACT_EPISODE:
            episode_id = str(job.payload["episode_id"])
            await self._write.extract_episode(episode_id, utc_now())
            return
        if job.type == JobType.PROJECT_GRAPH:
            memory_version_id = str(job.payload["memory_version_id"])
            memory = await self._store.get_memory_version_by_id(memory_version_id)
            if memory is None:
                msg = f"memory version {memory_version_id!r} not found for graph projection"
                raise RuntimeError(msg)
            relations = [
                ExtractedGraphRelation.model_validate(raw)
                for raw in job.payload.get("relations", [])
            ]
            await self._graph_projection.project_memory(memory=memory, relations=relations)


class Memory(Memrise):
    """Compatibility alias for the public Memrise SDK class."""


def to_memory_summary(memory: object) -> MemorySummary:
    from memrise.core.models import CanonicalMemory

    canonical = memory if isinstance(memory, CanonicalMemory) else None
    if canonical is None:
        msg = "expected canonical memory"
        raise TypeError(msg)
    return memory_to_summary(canonical)


__all__ = ["Memory", "Memrise", "to_job_summary", "to_memory_summary"]
