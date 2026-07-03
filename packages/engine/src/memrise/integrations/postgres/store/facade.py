from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.enums import CandidateStageStatus
from memrise.core.models import (
    ApplyCandidateOutcome,
    CanonicalMemory,
    Episode,
    EpisodeSaveOutcome,
    Feedback,
    MemoryCandidateStage,
    MemorySource,
    RetrievalItem,
    RetrievalTrace,
    Scope,
)
from memrise.integrations.postgres.store.candidate import PostgresCandidateRepository
from memrise.integrations.postgres.store.episode import PostgresEpisodeRepository
from memrise.integrations.postgres.store.graph_projection import PostgresGraphProjectionRepository
from memrise.integrations.postgres.store.memory import PostgresMemoryRepository
from memrise.integrations.postgres.store.retrieval import PostgresRetrievalRepository
from memrise.learning.apply import MemoryApplyService
from memrise.learning.policy import DefaultFeedbackPolicy
from memrise.learning.reconciliation import Reconciler
from memrise.ports.ids import IdGenerator
from memrise.ports.providers import ExtractedGraphRelation, ExtractedMemoryCandidate


class PostgresMemoryStore:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        id_generator: IdGenerator,
    ) -> None:
        apply_service = MemoryApplyService(
            reconciler=Reconciler(),
            feedback_policy=DefaultFeedbackPolicy(),
            id_generator=id_generator,
        )
        self._episodes = PostgresEpisodeRepository(session_factory)
        self._memories = PostgresMemoryRepository(session_factory, apply_service=apply_service)
        self._candidates = PostgresCandidateRepository(session_factory)
        self._retrievals = PostgresRetrievalRepository(session_factory, apply_service=apply_service)
        self._graph_projection = PostgresGraphProjectionRepository(
            session_factory,
            id_generator=id_generator,
        )

    async def save_episode(self, episode: Episode) -> EpisodeSaveOutcome:
        return await self._episodes.save_episode(episode)

    async def get_episode(self, episode_id: str) -> Episode | None:
        return await self._episodes.get_episode(episode_id)

    async def list_session_episodes(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        session_id: str,
    ) -> list[Episode]:
        return await self._episodes.list_session_episodes(
            namespace_id=namespace_id,
            agent_id=agent_id,
            session_id=session_id,
        )

    async def list_active_memories(
        self,
        *,
        scope: Scope,
        include_contested: bool = False,
        user_id_is_wildcard: bool = False,
        project_id_is_wildcard: bool = False,
    ) -> list[CanonicalMemory]:
        return await self._memories.list_active_memories(
            scope=scope,
            include_contested=include_contested,
            user_id_is_wildcard=user_id_is_wildcard,
            project_id_is_wildcard=project_id_is_wildcard,
        )

    async def list_memory_history(self, memory_id: str) -> list[CanonicalMemory]:
        return await self._memories.list_memory_history(memory_id)

    async def find_current_memory(
        self,
        *,
        scope: Scope,
        subject: str,
        key: str,
    ) -> CanonicalMemory | None:
        return await self._memories.find_current_memory(
            scope=scope,
            subject=subject,
            key=key,
        )

    async def apply_candidate(
        self,
        *,
        scope: Scope,
        candidate: ExtractedMemoryCandidate,
        source_episode_ids: list[str],
        embedding: list[float],
    ) -> ApplyCandidateOutcome:
        return await self._memories.apply_candidate(
            scope=scope,
            candidate=candidate,
            source_episode_ids=source_episode_ids,
            embedding=embedding,
        )

    async def list_candidate_stages_for_episode(
        self, episode_id: str
    ) -> list[MemoryCandidateStage]:
        return await self._candidates.list_candidate_stages_for_episode(episode_id)

    async def get_candidate_stage(self, candidate_stage_id: str) -> MemoryCandidateStage | None:
        return await self._candidates.get_candidate_stage(candidate_stage_id)

    async def save_candidate_stage(self, stage: MemoryCandidateStage) -> str:
        return await self._candidates.save_candidate_stage(stage)

    async def update_candidate_stage(
        self,
        candidate_stage_id: str,
        *,
        status: CandidateStageStatus,
        memory_version_id: str | None = None,
        rejection_reason: str | None = None,
    ) -> None:
        await self._candidates.update_candidate_stage(
            candidate_stage_id,
            status=status,
            memory_version_id=memory_version_id,
            rejection_reason=rejection_reason,
        )

    async def get_memory_version_by_id(self, memory_version_id: str) -> CanonicalMemory | None:
        return await self._memories.get_memory_version_by_id(memory_version_id)

    async def schedule_graph_projection(
        self,
        *,
        memory: CanonicalMemory,
        relations: list[ExtractedGraphRelation],
    ) -> str | None:
        return await self._graph_projection.schedule_graph_projection(
            memory=memory,
            relations=relations,
        )

    async def save_retrieval_trace(
        self,
        trace: RetrievalTrace,
        items: list[RetrievalItem],
    ) -> None:
        await self._retrievals.save_retrieval_trace(trace, items)

    async def save_feedback(self, feedback: Feedback) -> float | None:
        return await self._retrievals.save_feedback(feedback)

    async def get_retrieval_items(self, retrieval_id: str) -> list[RetrievalItem]:
        return await self._retrievals.get_retrieval_items(retrieval_id)

    async def list_memory_sources(self, memory_version_id: str) -> list[MemorySource]:
        return await self._memories.list_memory_sources(memory_version_id)

    async def list_recent_retrievals(
        self, *, namespace_id: str, limit: int
    ) -> list[RetrievalTrace]:
        return await self._retrievals.list_recent_retrievals(
            namespace_id=namespace_id,
            limit=limit,
        )
