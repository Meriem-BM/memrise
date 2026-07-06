from datetime import datetime

from memrise.consolidation.duplicates import find_duplicate_clusters
from memrise.core.models import Scope
from memrise.ports.repositories import MemoryStore


async def merge_scope_duplicates(store: MemoryStore, *, scope: Scope, now: datetime) -> int:
    """Merge near-duplicate active memories within one scope. Returns count superseded."""
    memories = await store.list_active_memories(scope=scope)
    clusters = find_duplicate_clusters(memories)
    superseded = 0
    for cluster in clusters:
        superseded += await store.supersede_memories_as_duplicates(
            survivor_version_id=cluster.survivor.version.id,
            duplicate_version_ids=[duplicate.version.id for duplicate in cluster.duplicates],
            now=now,
        )
    return superseded


class MemoryDedupeService:
    """Periodic safety net: sweep every active scope and merge near-duplicates.

    Write-time prevention stops most duplicates from being created, but concurrent
    writes and pre-existing backlog can still leave duplicates behind. This runs as
    the DEDUPE_MEMORIES background job on its own interval, independent of the
    cheaper bulk lifecycle sweep.
    """

    def __init__(self, *, store: MemoryStore) -> None:
        self._store = store

    async def run(self, now: datetime) -> int:
        total = 0
        for scope in await self._store.list_active_scopes():
            total += await merge_scope_duplicates(self._store, scope=scope, now=now)
        return total
