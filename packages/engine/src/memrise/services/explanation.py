from memrise.core.models import CanonicalMemory
from memrise.ports.repositories import MemoryStore
from memrise.schemas.responses import MemoryExplanation, MemorySummary


def to_summary(memory: CanonicalMemory) -> MemorySummary:
    return MemorySummary(
        memory_id=memory.identity.id,
        memory_version_id=memory.version.id,
        type=memory.identity.type,
        subject=memory.identity.subject,
        key=memory.identity.key,
        content=memory.version.content,
        status=memory.version.status,
        criticality=memory.version.criticality,
        usefulness_score=memory.version.usefulness_score,
        created_at=memory.version.created_at,
        valid_until=memory.version.valid_until,
    )


class ExplanationService:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def explain(self, memory_id: str) -> MemoryExplanation:
        history = await self._store.list_memory_history(memory_id)
        current = next((memory for memory in history if memory.version.is_lifecycle_active), None)
        provenance: list[str] = []
        for memory in history:
            sources = await self._store.list_memory_sources(memory.version.id)
            provenance.extend(source.episode_id for source in sources)
        return MemoryExplanation(
            memory_id=memory_id,
            current_version=to_summary(current) if current else None,
            versions=[to_summary(memory) for memory in history],
            provenance_episode_ids=sorted(set(provenance)),
            graph_edges=[],
            retrieval_feedback=[],
        )
