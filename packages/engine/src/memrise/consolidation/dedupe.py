from datetime import datetime

from memrise.consolidation.duplicates import (
    DuplicateCluster,
    clusters_from_confirmed_pairs,
    find_duplicate_candidate_pairs,
    find_duplicate_clusters,
)
from memrise.core.models import Scope
from memrise.ports.providers import CompletionProvider
from memrise.ports.repositories import MemoryStore


async def _supersede_clusters(
    store: MemoryStore, clusters: list[DuplicateCluster], *, now: datetime
) -> int:
    superseded = 0
    for cluster in clusters:
        superseded += await store.supersede_memories_as_duplicates(
            survivor_version_id=cluster.survivor.version.id,
            duplicate_version_ids=[duplicate.version.id for duplicate in cluster.duplicates],
            now=now,
        )
    return superseded


async def merge_scope_duplicates(store: MemoryStore, *, scope: Scope, now: datetime) -> int:
    """Embedding-only merge of near-duplicate active memories in one scope."""
    memories = await store.list_active_memories(scope=scope)
    clusters = find_duplicate_clusters(memories)
    return await _supersede_clusters(store, clusters, now=now)


class MemoryDedupeService:
    """Periodic safety net: sweep every active scope and merge near-duplicates.

    Two tiers. First, an embedding auto-merge collapses memories the model scores
    as clearly the same. Then, when a completion provider is configured, an LLM
    equivalence judge decides the ambiguous middle band where embeddings are
    unreliable (text-embedding-v4 compresses paraphrases), catching duplicates
    like differently phrased rules that cosine alone cannot separate from distinct
    facts. Write-time prevention still stops most duplicates before they are ever
    created; this cleans up the rest, including pre-existing backlog.
    """

    def __init__(
        self,
        *,
        store: MemoryStore,
        completion_provider: CompletionProvider | None = None,
    ) -> None:
        self._store = store
        self._completion_provider = completion_provider

    async def run(self, now: datetime) -> int:
        total = 0
        for scope in await self._store.list_active_scopes():
            total += await self._dedupe_scope(scope, now)
        return total

    async def _dedupe_scope(self, scope: Scope, now: datetime) -> int:
        superseded = await merge_scope_duplicates(self._store, scope=scope, now=now)
        if self._completion_provider is not None:
            superseded += await self._judge_and_merge(scope, now)
        return superseded

    async def _judge_and_merge(self, scope: Scope, now: datetime) -> int:
        assert self._completion_provider is not None
        # Re-fetch so tier-1 survivors are the pool the judge reasons over.
        memories = await self._store.list_active_memories(scope=scope)
        candidates = find_duplicate_candidate_pairs(memories)
        if not candidates:
            return 0
        result = await self._completion_provider.judge_duplicate_pairs(
            pairs=[
                {
                    "left_id": pair.left.version.id,
                    "left_content": pair.left.version.content,
                    "right_id": pair.right.version.id,
                    "right_content": pair.right.version.content,
                }
                for pair in candidates
            ],
            context={
                "namespace_id": scope.namespace_id,
                "agent_id": scope.agent_id,
                "project_id": scope.project_id,
            },
        )
        confirmed = {
            (verdict.left_id, verdict.right_id) for verdict in result.verdicts if verdict.equivalent
        }
        clusters = clusters_from_confirmed_pairs(memories, confirmed)
        return await _supersede_clusters(self._store, clusters, now=now)
