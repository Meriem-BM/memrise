from dataclasses import dataclass

from memrise.core.embeddings import cosine_similarity
from memrise.core.models import CanonicalMemory

# Pairs whose cosine sits in this band are too close to be clearly distinct but
# too far to auto-merge, so an LLM equivalence judge decides. text-embedding-v4
# compresses paraphrases (differently phrased rules can score ~0.60), so the floor
# is deliberately low; the judge, not the embedding, is the precision layer here.
JUDGE_CANDIDATE_FLOOR = 0.45
# Cap LLM work per scope per run so the judge stays cheap regardless of scope size.
MAX_JUDGE_PAIRS = 40

# Above this cosine similarity, two same-scope memories are treated as saying the
# same thing and merged into one survivor. Tuned against real text-embedding-v4
# vectors, whose paraphrase similarities are compressed: clean paraphrases land
# ~0.85-0.90 while distinct same-topic facts top out ~0.72, so this sits in that
# gap. It errs toward precision: hard paraphrases the model scores low (e.g.
# differently phrased rules at ~0.60) are left for reconciliation and, in future,
# an LLM equivalence judge. Single-linkage bridges paraphrases individually just
# under the bar.
MERGE_SIMILARITY_THRESHOLD = 0.85


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
    """Group same-scope memories whose embeddings are near-identical.

    Uses single-linkage: a memory joins a cluster when it is within ``threshold``
    cosine similarity of ANY member, not just the seed. This matters for real
    paraphrases, where A~B and B~C can both clear the bar while A~C sits just
    under it, so C would otherwise escape the merge. The strongest memory
    (usefulness+confidence, then newest version) seeds each cluster and survives.

    Pure and deterministic so it can be unit-tested without a database or model.
    Only memories carrying an embedding from the same model are comparable.
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
        members = [(seed, seed_vector)]
        member_ids = {seed.version.id}
        grew = True
        while grew:
            grew = False
            for other, other_vector in ordered:
                if other.version.id in assigned or other.version.id in member_ids:
                    continue
                if seed.version.embedding_model != other.version.embedding_model:
                    continue
                if not _same_scope(seed, other):
                    continue
                if any(
                    cosine_similarity(member_vector, other_vector) >= threshold
                    for _, member_vector in members
                ):
                    members.append((other, other_vector))
                    member_ids.add(other.version.id)
                    grew = True
        duplicates = [memory for memory, _ in members if memory.version.id != seed.version.id]
        if duplicates:
            assigned.update(member_ids)
            clusters.append(DuplicateCluster(survivor=seed, duplicates=duplicates))
    return clusters


@dataclass(frozen=True, slots=True)
class CandidatePair:
    left: CanonicalMemory
    right: CanonicalMemory
    similarity: float


def find_duplicate_candidate_pairs(
    memories: list[CanonicalMemory],
    *,
    floor: float = JUDGE_CANDIDATE_FLOOR,
    ceiling: float = MERGE_SIMILARITY_THRESHOLD,
    limit: int = MAX_JUDGE_PAIRS,
) -> list[CandidatePair]:
    """Same-scope, same-model pairs whose cosine sits in the uncertain band.

    Above ``ceiling`` the embedding auto-merges; below ``floor`` the memories are
    treated as unrelated. Pairs in between are ambiguous to the embedding, so they
    are handed to the LLM equivalence judge. Highest-similarity pairs come first
    and the list is capped at ``limit`` to bound model cost.
    """
    embeddable = [
        (memory, embedding)
        for memory in memories
        if (embedding := memory.version.embedding) is not None
    ]
    pairs: list[CandidatePair] = []
    for i in range(len(embeddable)):
        left, left_vector = embeddable[i]
        for j in range(i + 1, len(embeddable)):
            right, right_vector = embeddable[j]
            if left.version.embedding_model != right.version.embedding_model:
                continue
            if not _same_scope(left, right):
                continue
            similarity = cosine_similarity(left_vector, right_vector)
            if floor <= similarity < ceiling:
                pairs.append(CandidatePair(left=left, right=right, similarity=similarity))
    pairs.sort(key=lambda pair: pair.similarity, reverse=True)
    return pairs[:limit]


def clusters_from_confirmed_pairs(
    memories: list[CanonicalMemory],
    confirmed: set[tuple[str, str]],
) -> list[DuplicateCluster]:
    """Build merge clusters from LLM-confirmed equivalent pairs (connected components).

    Pairs are undirected; each connected component becomes one cluster whose
    strongest member survives. Only version ids present in ``memories`` are used.
    """
    by_id = {memory.version.id: memory for memory in memories}
    adjacency: dict[str, set[str]] = {}
    for left_id, right_id in confirmed:
        if left_id not in by_id or right_id not in by_id or left_id == right_id:
            continue
        adjacency.setdefault(left_id, set()).add(right_id)
        adjacency.setdefault(right_id, set()).add(left_id)

    seen: set[str] = set()
    clusters: list[DuplicateCluster] = []
    for start_id in adjacency:
        if start_id in seen:
            continue
        component: list[str] = []
        stack = [start_id]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(current)
            stack.extend(adjacency[current] - seen)
        if len(component) < 2:
            continue
        members = sorted((by_id[vid] for vid in component), key=_strength, reverse=True)
        clusters.append(DuplicateCluster(survivor=members[0], duplicates=members[1:]))
    return clusters
