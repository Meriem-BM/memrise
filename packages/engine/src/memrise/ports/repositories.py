from datetime import datetime
from typing import Protocol

from memrise.core.enums import CandidateStageStatus, FeedbackOutcome, FeedbackSource, JobType
from memrise.core.models import (
    ApplyCandidateOutcome,
    BackgroundJob,
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
from memrise.ports.providers import (
    EmbeddingVector,
    ExtractedGraphRelation,
    ExtractedMemoryCandidate,
)


class MemoryStore(Protocol):
    async def save_episode(self, episode: Episode) -> EpisodeSaveOutcome: ...

    async def get_episode(self, episode_id: str) -> Episode | None: ...

    async def list_session_episodes(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        session_id: str,
    ) -> list[Episode]: ...

    async def list_active_memories(
        self,
        *,
        scope: Scope,
        include_contested: bool = False,
        user_id_is_wildcard: bool = False,
        project_id_is_wildcard: bool = False,
    ) -> list[CanonicalMemory]: ...

    async def list_memory_history(self, memory_id: str) -> list[CanonicalMemory]: ...

    async def list_critical_memories(
        self,
        *,
        scope: Scope,
        limit: int,
    ) -> list[CanonicalMemory]: ...

    async def search_structured(
        self,
        *,
        scope: Scope,
        query: str,
        limit: int,
    ) -> list[CanonicalMemory]: ...

    async def get_memories_by_version_ids(
        self,
        *,
        scope: Scope,
        version_ids: list[str],
    ) -> list[CanonicalMemory]: ...

    async def search_lexical(
        self,
        *,
        scope: Scope,
        query: str,
        limit: int,
    ) -> list[tuple[CanonicalMemory, float]]: ...

    async def search_semantic(
        self,
        *,
        scope: Scope,
        embedding: EmbeddingVector,
        limit: int,
    ) -> list[tuple[CanonicalMemory, float]]: ...

    async def find_current_memory(
        self,
        *,
        scope: Scope,
        subject: str,
        key: str,
    ) -> CanonicalMemory | None: ...

    async def apply_candidate(
        self,
        *,
        scope: Scope,
        candidate: ExtractedMemoryCandidate,
        source_episode_ids: list[str],
        embedding: EmbeddingVector,
    ) -> ApplyCandidateOutcome: ...

    async def list_candidate_stages_for_episode(
        self, episode_id: str
    ) -> list[MemoryCandidateStage]: ...

    async def get_candidate_stage(self, candidate_stage_id: str) -> MemoryCandidateStage | None: ...

    async def save_candidate_stage(self, stage: MemoryCandidateStage) -> str: ...

    async def update_candidate_stage(
        self,
        candidate_stage_id: str,
        *,
        status: CandidateStageStatus,
        memory_version_id: str | None = None,
        rejection_reason: str | None = None,
    ) -> None: ...

    async def get_memory_version_by_id(self, memory_version_id: str) -> CanonicalMemory | None: ...

    async def schedule_graph_projection(
        self,
        *,
        memory: CanonicalMemory,
        relations: list[ExtractedGraphRelation],
    ) -> str | None: ...

    async def save_retrieval_trace(
        self,
        trace: RetrievalTrace,
        items: list[RetrievalItem],
    ) -> None: ...

    async def save_feedback(self, feedback: Feedback) -> float | None: ...

    async def get_retrieval_items(self, retrieval_id: str) -> list[RetrievalItem]: ...

    async def list_memory_sources(self, memory_version_id: str) -> list[MemorySource]: ...

    async def list_recent_retrievals(
        self, *, namespace_id: str, limit: int
    ) -> list[RetrievalTrace]: ...

    async def expire_due_memories(self, *, now: datetime) -> int: ...

    async def decay_usefulness(
        self,
        *,
        now: datetime,
        half_life_days: float,
        min_elapsed_seconds: int,
    ) -> int: ...

    async def resolve_contested(self, *, now: datetime, margin: float) -> int: ...


class JobQueue(Protocol):
    async def enqueue(
        self,
        *,
        job_type: JobType,
        payload: dict[str, object],
        dedupe_key: str | None = None,
    ) -> str: ...

    async def find_job_id_by_dedupe_key(self, dedupe_key: str) -> str | None: ...

    async def claim_next(self, *, worker_id: str) -> BackgroundJob | None: ...

    async def get_job(self, job_id: str) -> BackgroundJob | None: ...

    async def complete(self, job_id: str) -> None: ...

    async def fail(self, job_id: str, error: str) -> None: ...


class FeedbackPolicy(Protocol):
    def confidence_for(self, source: FeedbackSource, provided: float | None) -> float: ...

    def usefulness_delta(self, outcome: FeedbackOutcome, confidence: float) -> float: ...
