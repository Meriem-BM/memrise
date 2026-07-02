from typing import Protocol

from memrise.core.enums import FeedbackOutcome, FeedbackSource, JobType
from memrise.core.models import (
    BackgroundJob,
    CanonicalMemory,
    Episode,
    Feedback,
    GraphEdge,
    GraphNode,
    MemorySource,
    RetrievalItem,
    RetrievalTrace,
    Scope,
)
from memrise.ports.providers import ExtractedMemoryCandidate


class MemoryStore(Protocol):
    async def save_episode(self, episode: Episode) -> None: ...

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
    ) -> list[CanonicalMemory]: ...

    async def list_memory_history(self, memory_id: str) -> list[CanonicalMemory]: ...

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
        embedding: list[float],
    ) -> CanonicalMemory | None: ...

    async def save_graph_projection(
        self,
        *,
        memory: CanonicalMemory,
        relations: list[tuple[str, str, str]],
    ) -> list[GraphEdge]: ...

    async def list_graph_neighborhood(
        self,
        *,
        scope: Scope,
        query: str | None,
        hops: int,
    ) -> tuple[list[GraphNode], list[GraphEdge]]: ...

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


class JobQueue(Protocol):
    async def enqueue(
        self,
        *,
        job_type: JobType,
        payload: dict[str, object],
        dedupe_key: str | None = None,
    ) -> str: ...

    async def claim_next(self, *, worker_id: str) -> BackgroundJob | None: ...

    async def complete(self, job_id: str) -> None: ...

    async def fail(self, job_id: str, error: str) -> None: ...


class FeedbackPolicy(Protocol):
    def confidence_for(self, source: FeedbackSource, provided: float | None) -> float: ...

    def usefulness_delta(self, outcome: FeedbackOutcome, confidence: float) -> float: ...
