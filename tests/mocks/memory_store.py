from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime

from memrise.core.enums import Criticality, JobStatus, JobType, MemoryStatus, MemoryType
from memrise.core.models import (
    BackgroundJob,
    CanonicalMemory,
    Episode,
    Feedback,
    MemoryIdentity,
    MemorySource,
    MemoryVersion,
    RetrievalItem,
    RetrievalTrace,
    Scope,
)
from memrise.learning.apply import MemoryApplyService
from memrise.learning.policy import DefaultFeedbackPolicy
from memrise.learning.reconciliation import Reconciler
from memrise.ports.ids import IdGenerator
from memrise.ports.providers import ExtractedGraphRelation, ExtractedMemoryCandidate
from memrise.runtime.ids import UuidGenerator


def _utc_now() -> datetime:
    return datetime.now(UTC)


def make_memory(
    *,
    memory_id: str = "mem_test",
    version_id: str = "memv_test",
    namespace_id: str = "ns",
    agent_id: str = "agent",
    user_id: str | None = "user",
    project_id: str | None = "atlas",
    subject: str = "Atlas",
    key: str = "package_manager",
    content: str = "Atlas uses pnpm for dependencies.",
    confidence: float = 0.9,
    importance: float = 0.7,
    usefulness_score: float = 0.5,
    criticality: Criticality = Criticality.NORMAL,
    status: MemoryStatus = MemoryStatus.ACTIVE,
    version_number: int = 1,
) -> CanonicalMemory:
    now = _utc_now()
    identity = MemoryIdentity(
        id=memory_id,
        namespace_id=namespace_id,
        agent_id=agent_id,
        user_id=user_id,
        project_id=project_id,
        type=MemoryType.FACT,
        subject=subject,
        key=key,
        created_at=now,
    )
    version = MemoryVersion(
        id=version_id,
        memory_id=memory_id,
        version_number=version_number,
        content=content,
        structured_value={},
        status=status,
        confidence=confidence,
        importance=importance,
        criticality=criticality,
        usefulness_score=usefulness_score,
        valid_from=now,
        created_at=now,
    )
    return CanonicalMemory(identity=identity, version=version)


@dataclass
class MemoryStoreStub:
    episodes: dict[str, Episode] = field(default_factory=dict)
    memories: list[CanonicalMemory] = field(default_factory=list)
    sources: dict[str, list[MemorySource]] = field(default_factory=dict)
    retrieval_traces: dict[str, RetrievalTrace] = field(default_factory=dict)
    retrieval_items: dict[str, list[RetrievalItem]] = field(default_factory=dict)
    feedback: list[Feedback] = field(default_factory=list)
    jobs: list[BackgroundJob] = field(default_factory=list)
    graph_projection_jobs: list[str] = field(default_factory=list)
    id_generator: IdGenerator = field(default_factory=UuidGenerator)

    def _apply_service(self) -> MemoryApplyService:
        return MemoryApplyService(
            reconciler=Reconciler(),
            feedback_policy=DefaultFeedbackPolicy(),
            id_generator=self.id_generator,
        )

    async def save_episode(self, episode: Episode) -> None:
        self.episodes[episode.id] = episode

    async def get_episode(self, episode_id: str) -> Episode | None:
        return self.episodes.get(episode_id)

    async def list_session_episodes(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        session_id: str,
    ) -> list[Episode]:
        return [
            episode
            for episode in self.episodes.values()
            if episode.namespace_id == namespace_id
            and episode.agent_id == agent_id
            and episode.session_id == session_id
        ]

    async def list_active_memories(
        self,
        *,
        scope: Scope,
        include_contested: bool = False,
        user_id_is_wildcard: bool = False,
        project_id_is_wildcard: bool = False,
    ) -> list[CanonicalMemory]:
        del include_contested
        results: list[CanonicalMemory] = []
        for memory in self.memories:
            identity = memory.identity
            if identity.namespace_id != scope.namespace_id or identity.agent_id != scope.agent_id:
                continue
            if (
                not user_id_is_wildcard
                and scope.user_id is not None
                and identity.user_id != scope.user_id
            ):
                continue
            if (
                not project_id_is_wildcard
                and scope.project_id is not None
                and identity.project_id != scope.project_id
            ):
                continue
            if memory.version.status == MemoryStatus.ACTIVE:
                results.append(memory)
        return results

    async def list_memory_history(self, memory_id: str) -> list[CanonicalMemory]:
        return [memory for memory in self.memories if memory.identity.id == memory_id]

    async def find_current_memory(
        self,
        *,
        scope: Scope,
        subject: str,
        key: str,
    ) -> CanonicalMemory | None:
        active = await self.list_active_memories(scope=scope)
        for memory in active:
            if memory.identity.subject == subject and memory.identity.key == key:
                return memory
        return None

    async def apply_candidate(
        self,
        *,
        scope: Scope,
        candidate: ExtractedMemoryCandidate,
        source_episode_ids: list[str],
        embedding: list[float],
    ) -> CanonicalMemory | None:
        existing = await self.find_current_memory(
            scope=scope,
            subject=candidate.subject,
            key=candidate.key,
        )
        plan = self._apply_service().plan_candidate(
            scope=scope,
            candidate=candidate,
            existing=existing,
            source_episode_ids=source_episode_ids,
            embedding=embedding,
            now=_utc_now(),
        )
        if plan is None:
            return existing
        if plan.reinforce is not None and existing is not None:
            updated = make_memory(
                memory_id=existing.identity.id,
                version_id=existing.version.id,
                namespace_id=existing.identity.namespace_id,
                agent_id=existing.identity.agent_id,
                user_id=existing.identity.user_id,
                project_id=existing.identity.project_id,
                subject=existing.identity.subject,
                key=existing.identity.key,
                content=existing.version.content,
                confidence=plan.reinforce.confidence,
                importance=existing.version.importance,
                usefulness_score=plan.reinforce.usefulness_score,
                criticality=existing.version.criticality,
                status=existing.version.status,
                version_number=existing.version.version_number,
            )
            self.memories = [
                updated if memory.version.id == existing.version.id else memory
                for memory in self.memories
            ]
            for episode_id in plan.reinforce.source_episode_ids:
                self.sources.setdefault(existing.version.id, []).append(
                    MemorySource(
                        memory_version_id=existing.version.id,
                        episode_id=episode_id,
                        relation="source",
                    )
                )
            return updated
        if plan.new_version is None:
            return existing
        new_version = plan.new_version
        version_id = self._apply_service().new_version_id()
        memory = make_memory(
            memory_id=new_version.memory_id or self.id_generator.new_id("mem"),
            version_id=version_id,
            namespace_id=scope.namespace_id,
            agent_id=scope.agent_id,
            user_id=scope.user_id,
            project_id=scope.project_id,
            subject=new_version.candidate.subject,
            key=new_version.candidate.key,
            content=new_version.candidate.content,
            confidence=new_version.candidate.confidence,
            importance=new_version.candidate.importance,
            usefulness_score=0.5,
            criticality=new_version.candidate.criticality,
            status=new_version.new_version_status,
            version_number=new_version.version_number,
        )
        if new_version.supersede_existing_version_id is not None:
            self.memories = [
                make_memory(
                    memory_id=item.identity.id,
                    version_id=item.version.id,
                    namespace_id=item.identity.namespace_id,
                    agent_id=item.identity.agent_id,
                    user_id=item.identity.user_id,
                    project_id=item.identity.project_id,
                    subject=item.identity.subject,
                    key=item.identity.key,
                    content=item.version.content,
                    confidence=item.version.confidence,
                    importance=item.version.importance,
                    usefulness_score=item.version.usefulness_score,
                    criticality=item.version.criticality,
                    status=new_version.supersede_existing_status or item.version.status,
                    version_number=item.version.version_number,
                )
                if item.version.id == new_version.supersede_existing_version_id
                else item
                for item in self.memories
            ]
        self.memories.append(memory)
        for episode_id in new_version.source_episode_ids:
            self.sources.setdefault(memory.version.id, []).append(
                MemorySource(
                    memory_version_id=memory.version.id,
                    episode_id=episode_id,
                    relation="source",
                )
            )
        return memory

    async def get_memory_version_by_id(self, memory_version_id: str) -> CanonicalMemory | None:
        for memory in self.memories:
            if memory.version.id == memory_version_id:
                return memory
        return None

    async def schedule_graph_projection(
        self,
        *,
        memory: CanonicalMemory,
        relations: list[ExtractedGraphRelation],
    ) -> str | None:
        if not relations:
            return None
        job_id = self.id_generator.new_id("job")
        self.graph_projection_jobs.append(job_id)
        self.jobs.append(
            BackgroundJob(
                id=job_id,
                type=JobType.PROJECT_GRAPH,
                payload={
                    "memory_version_id": memory.version.id,
                    "relations": [relation.model_dump() for relation in relations],
                },
                status=JobStatus.PENDING,
                attempts=0,
                max_attempts=3,
                run_at=_utc_now(),
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
        )
        return job_id

    async def save_retrieval_trace(self, trace: RetrievalTrace, items: list[RetrievalItem]) -> None:
        self.retrieval_traces[trace.id] = trace
        self.retrieval_items[trace.id] = deepcopy(items)

    async def save_feedback(self, feedback: Feedback) -> float | None:
        self.feedback.append(feedback)
        if feedback.memory_version_id is None:
            return None
        memory = await self.get_memory_version_by_id(feedback.memory_version_id)
        if memory is None:
            return None
        delta = DefaultFeedbackPolicy().usefulness_delta(feedback.outcome, feedback.confidence)
        updated_score = min(1.0, max(0.0, memory.version.usefulness_score + delta))
        self.memories = [
            make_memory(
                memory_id=item.identity.id,
                version_id=item.version.id,
                namespace_id=item.identity.namespace_id,
                agent_id=item.identity.agent_id,
                user_id=item.identity.user_id,
                project_id=item.identity.project_id,
                subject=item.identity.subject,
                key=item.identity.key,
                content=item.version.content,
                confidence=item.version.confidence,
                importance=item.version.importance,
                usefulness_score=updated_score,
                criticality=item.version.criticality,
                status=item.version.status,
                version_number=item.version.version_number,
            )
            if item.version.id == memory.version.id
            else item
            for item in self.memories
        ]
        return updated_score

    async def get_retrieval_items(self, retrieval_id: str) -> list[RetrievalItem]:
        return list(self.retrieval_items.get(retrieval_id, []))

    async def list_memory_sources(self, memory_version_id: str) -> list[MemorySource]:
        return list(self.sources.get(memory_version_id, []))

    async def list_recent_retrievals(
        self, *, namespace_id: str, limit: int
    ) -> list[RetrievalTrace]:
        traces = [
            trace for trace in self.retrieval_traces.values() if trace.namespace_id == namespace_id
        ]
        traces.sort(key=lambda trace: trace.created_at, reverse=True)
        return traces[:limit]


@dataclass
class ExplanationMemoryStore(MemoryStoreStub):
    history_by_memory_id: dict[str, list[CanonicalMemory]] = field(default_factory=dict)
    sources_by_version_id: dict[str, list[MemorySource]] = field(default_factory=dict)

    async def list_memory_history(self, memory_id: str) -> list[CanonicalMemory]:
        return list(self.history_by_memory_id.get(memory_id, []))

    async def list_memory_sources(self, memory_version_id: str) -> list[MemorySource]:
        return list(self.sources_by_version_id.get(memory_version_id, []))
