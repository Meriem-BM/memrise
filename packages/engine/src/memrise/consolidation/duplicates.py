from dataclasses import dataclass

from memrise.core.embeddings import cosine_similarity
from memrise.core.models import CanonicalMemory

# Above this cosine similarity, two same-scope memories are treated as saying the
# same thing and merged into one survivor. Set high so that distinct or
# contradictory facts (e.g. "uses npm" vs "uses pnpm") stay separate and are left
# to reconciliation / the contested lifecycle.
MERGE_SIMILARITY_THRESHOLD = 0.93


@dataclass(frozen=True, slots=True)
class DuplicateCluster:
    survivor: CanonicalMemory
    duplicates: list[CanonicalMemory]


def _strength(memory: CanonicalMemory) -> tuple[float, int]:
    version = memory.version
    return (version.usefulness_score + version.confidence, version.version_number)


def _same_scope(a: CanonicalMemory, b: CanonicalMemory) -> bool:
    return (
        a.identity.user_id == b.identity.user_id and a.identity.project_id == b.identity.project_id
    )


def find_duplicate_clusters(
    memories: list[CanonicalMemory],
    *,
    threshold: float = MERGE_SIMILARITY_THRESHOLD,
) -> list[DuplicateCluster]:
    """Greedily group same-scope memories whose embeddings are near-identical.

    The strongest memory (usefulness+confidence, then newest version) seeds each
    cluster and survives; every other same-scope memory within ``threshold``
    cosine similarity becomes one of its duplicates. Pure and deterministic so it
    can be unit-tested without a database or model. Only memories that carry an
    embedding from the same model are comparable.
    """
    embeddable = [
        (memory, embedding)
        for memory in memories
        if (embedding := memory.version.embedding) is not None
    ]
    ordered = sorted(embeddable, key=lambda pair: _strength(pair[0]), reverse=True)
    assigned: set[str] = set()
    clusters: list[DuplicateCluster] = []
    for seed, seed_vector in ordered:
        if seed.version.id in assigned:
            continue
        duplicates: list[CanonicalMemory] = []
        for other, other_vector in ordered:
            if other.version.id == seed.version.id or other.version.id in assigned:
                continue
            if seed.version.embedding_model != other.version.embedding_model:
                continue
            if not _same_scope(seed, other):
                continue
            if cosine_similarity(seed_vector, other_vector) >= threshold:
                duplicates.append(other)
                assigned.add(other.version.id)
        if duplicates:
            assigned.add(seed.version.id)
            clusters.append(DuplicateCluster(survivor=seed, duplicates=duplicates))
    return clusters
