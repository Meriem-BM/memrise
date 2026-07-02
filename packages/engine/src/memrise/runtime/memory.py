from dataclasses import asdict

from memrise.core.enums import JobType
from memrise.core.models import BackgroundJob, Episode, Scope
from memrise.core.time import utc_now
from memrise.integrations.in_memory.providers import (
    DeterministicCompletionProvider,
    DeterministicEmbeddingProvider,
)
from memrise.integrations.in_memory.store import InMemoryStore, feedback_from_input
from memrise.ports.providers import CompletionProvider, EmbeddingProvider, TokenCounter
from memrise.ports.repositories import FeedbackPolicy, JobQueue, MemoryStore
from memrise.runtime.settings import MemorySettings
from memrise.schemas.requests import (
    CaptureRequest,
    ConsolidateRequest,
    FeedbackRequest,
    RetrieveRequest,
)
from memrise.schemas.responses import (
    CaptureResponse,
    ConsolidateResponse,
    FeedbackResponse,
    MemoryExplanation,
    RetrievedMemory,
    RetrieveResponse,
)
from memrise.services.clock import SystemClock
from memrise.services.explanation import ExplanationService
from memrise.services.ids import UuidGenerator
from memrise.services.importance import ImportanceGate
from memrise.services.outcome_learning import DefaultFeedbackPolicy
from memrise.services.retrieval import RetrievalService
from memrise.services.token_counter import ApproximateTokenCounter
from memrise.services.write_path import WriteService


class Memory:
    def __init__(
        self,
        *,
        store: MemoryStore,
        jobs: JobQueue,
        completion_provider: CompletionProvider,
        embedding_provider: EmbeddingProvider,
        token_counter: TokenCounter,
        feedback_policy: FeedbackPolicy,
    ) -> None:
        self._store = store
        self._jobs = jobs
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
        )
        self._retrieval = RetrievalService(
            store=store,
            embedding_provider=embedding_provider,
            token_counter=token_counter,
            ids=self._ids,
        )
        self._explain = ExplanationService(store)

    @classmethod
    def from_env(cls) -> Memory:
        settings = MemorySettings()
        if settings.database_url:
            from memrise.integrations.postgres.factory import build_postgres_memory

            return build_postgres_memory(settings)
        return cls.with_in_memory()

    @classmethod
    def with_in_memory(cls) -> Memory:
        store = InMemoryStore()
        embeddings = DeterministicEmbeddingProvider()
        return cls(
            store=store,
            jobs=store,
            completion_provider=DeterministicCompletionProvider(),
            embedding_provider=embeddings,
            token_counter=ApproximateTokenCounter(),
            feedback_policy=DefaultFeedbackPolicy(),
        )

    @property
    def store(self) -> MemoryStore:
        return self._store

    @property
    def jobs(self) -> JobQueue:
        return self._jobs

    async def capture(self, **kwargs: object) -> CaptureResponse:
        request = CaptureRequest.model_validate(kwargs)
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
            )
            job_id = await self._write.capture_episode(episode)
            episode_ids.append(episode.id)
            if job_id:
                job_ids.append(job_id)
        return CaptureResponse(episode_ids=episode_ids, job_ids=job_ids)

    async def retrieve(self, **kwargs: object) -> RetrieveResponse:
        request = RetrieveRequest.model_validate(kwargs)
        scope = Scope(
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
            critical=[await self._to_retrieved(memory, selected=True) for memory in critical],
            memories=[await self._to_retrieved(memory, selected=True) for memory in memories],
            context=context,
        )

    async def feedback(self, retrieval_id: str, **kwargs: object) -> FeedbackResponse:
        request = FeedbackRequest.model_validate(kwargs)
        confidence = self._feedback_policy.confidence_for(request.source, request.confidence)
        feedback = feedback_from_input(
            feedback_id=self._ids.new_id("feedback"),
            retrieval_id=retrieval_id,
            outcome=request.outcome,
            source=request.source,
            confidence=confidence,
            memory_version_id=request.memory_version_id,
            graph_edge_id=request.graph_edge_id,
            task_type=request.task_type,
        )
        score = await self._store.save_feedback(feedback)
        return FeedbackResponse(
            feedback_id=feedback.id,
            updated_memory_version_id=request.memory_version_id,
            updated_graph_edge_id=request.graph_edge_id,
            usefulness_score=score,
        )

    async def consolidate(self, **kwargs: object) -> ConsolidateResponse:
        request = ConsolidateRequest.model_validate(kwargs)
        job_id = await self._jobs.enqueue(
            job_type=JobType.CONSOLIDATE_SESSION,
            payload=request.model_dump(exclude_none=True),
            dedupe_key=f"consolidate:{request.namespace_id}:{request.agent_id}:{request.session_id}",
        )
        return ConsolidateResponse(job_id=job_id, accepted=True)

    async def explain(self, memory_id: str) -> MemoryExplanation:
        return await self._explain.explain(memory_id)

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

    async def _to_retrieved(self, memory: object, *, selected: bool) -> RetrievedMemory:
        from memrise.core.models import CanonicalMemory

        canonical = memory if isinstance(memory, CanonicalMemory) else None
        if canonical is None:
            msg = "expected canonical memory"
            raise TypeError(msg)
        sources = await self._store.list_memory_sources(canonical.version.id)
        return RetrievedMemory(
            memory_id=canonical.identity.id,
            memory_version_id=canonical.version.id,
            type=canonical.identity.type,
            subject=canonical.identity.subject,
            key=canonical.identity.key,
            content=canonical.version.content,
            status=canonical.version.status,
            criticality=canonical.version.criticality,
            confidence=canonical.version.confidence,
            importance=canonical.version.importance,
            usefulness_score=canonical.version.usefulness_score,
            token_count=self._token_counter.count(canonical.version.content),
            source_types=[],
            selected_for_context=selected,
            provenance_episode_ids=[source.episode_id for source in sources],
            explanation={"scope": asdict(canonical.identity.scope)},
        )
