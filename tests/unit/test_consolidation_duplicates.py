from datetime import UTC, datetime

from memrise.consolidation.duplicates import find_duplicate_clusters
from memrise.consolidation.session_consolidation import SessionConsolidationService
from memrise.core.enums import MemoryStatus
from memrise.core.models import Scope
from tests.mocks.memory_store import MemoryStoreStub, make_memory

NOW = datetime(2026, 7, 5, tzinfo=UTC)
MODEL = "mock-embedding"


def _mem(version_id: str, *, subject: str, key: str, vector: list[float], **kwargs: object):  # type: ignore[no-untyped-def]
    return make_memory(
        memory_id=f"mem_{version_id}",
        version_id=version_id,
        subject=subject,
        key=key,
        embedding=vector,
        embedding_model=MODEL,
        **kwargs,  # type: ignore[arg-type]
    )


def test_find_duplicate_clusters_groups_near_identical() -> None:
    a = _mem("memv_a", subject="lockfile", key="rule", vector=[1.0, 0.0, 0.0], confidence=0.9)
    b = _mem(
        "memv_b", subject="pnpm_lockfile", key="edit", vector=[0.99, 0.01, 0.0], confidence=0.7
    )
    distinct = _mem("memv_c", subject="pm", key="choice", vector=[0.0, 1.0, 0.0], confidence=0.8)

    clusters = find_duplicate_clusters([a, b, distinct])

    assert len(clusters) == 1
    cluster = clusters[0]
    # Strongest (higher usefulness+confidence) survives; the distinct fact is untouched.
    assert cluster.survivor.version.id == "memv_a"
    assert [d.version.id for d in cluster.duplicates] == ["memv_b"]


def test_find_duplicate_clusters_uses_single_linkage() -> None:
    # Real-embedding case: A~B and B~C clear the bar, but A~C sits just under it.
    # C must still merge, linked through B, or it escapes the cluster.
    # Unit vectors at 0deg, 15deg, 30deg: adjacent steps clear cos15=0.966 >= 0.93,
    # but the ends sit at cos30=0.866 < 0.93.
    a = _mem("memv_a", subject="lockfile", key="rule", vector=[1.0, 0.0], confidence=0.95)
    b = _mem("memv_b", subject="pnpm_lock", key="edit", vector=[0.96593, 0.25882], confidence=0.7)
    c = _mem("memv_c", subject="gen_lock", key="edits", vector=[0.86603, 0.5], confidence=0.6)

    # Sanity: A~C is below the default threshold while A~B and B~C are above it.
    from memrise.consolidation.duplicates import MERGE_SIMILARITY_THRESHOLD
    from memrise.core.embeddings import cosine_similarity

    va, vb, vc = a.version.embedding, b.version.embedding, c.version.embedding
    assert va is not None and vb is not None and vc is not None
    assert cosine_similarity(va, vc) < MERGE_SIMILARITY_THRESHOLD
    assert cosine_similarity(va, vb) >= MERGE_SIMILARITY_THRESHOLD
    assert cosine_similarity(vb, vc) >= MERGE_SIMILARITY_THRESHOLD

    clusters = find_duplicate_clusters([a, b, c])

    assert len(clusters) == 1
    assert clusters[0].survivor.version.id == "memv_a"
    assert {d.version.id for d in clusters[0].duplicates} == {"memv_b", "memv_c"}


def test_find_duplicate_clusters_ignores_cross_model_and_cross_scope() -> None:
    a = _mem("memv_a", subject="s", key="k", vector=[1.0, 0.0])
    other_model = make_memory(
        memory_id="mem_b",
        version_id="memv_b",
        subject="s2",
        key="k2",
        embedding=[1.0, 0.0],
        embedding_model="different-model",
    )
    other_scope = _mem("memv_c", subject="s3", key="k3", vector=[1.0, 0.0], project_id="other")

    assert find_duplicate_clusters([a, other_model, other_scope]) == []


async def test_merge_duplicates_supersedes_weaker_members() -> None:
    # Three phrasings of one rule (the screenshot's lockfile case) + one distinct fact.
    rule_a = _mem("memv_r1", subject="lockfile", key="rule", vector=[1.0, 0.0], confidence=0.95)
    rule_b = _mem("memv_r2", subject="pnpm_lock", key="edit", vector=[0.99, 0.02], confidence=0.7)
    rule_c = _mem(
        "memv_r3", subject="generated_lock", key="edit", vector=[0.98, 0.01], confidence=0.6
    )
    distinct = _mem("memv_d", subject="pm", key="choice", vector=[0.0, 1.0], confidence=0.8)
    store = MemoryStoreStub(memories=[rule_a, rule_b, rule_c, distinct])
    service = SessionConsolidationService(
        store=store,
        write=None,  # type: ignore[arg-type]
        completion_provider=None,  # type: ignore[arg-type]
        embedding_provider=None,  # type: ignore[arg-type]
    )
    scope = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")

    superseded = await service.merge_duplicates(scope=scope, now=NOW)

    assert superseded == 2
    by_id = {memory.version.id: memory for memory in store.memories}
    # Survivor and the distinct fact stay active; the two weaker duplicates are superseded.
    assert by_id["memv_r1"].version.status == MemoryStatus.ACTIVE
    assert by_id["memv_d"].version.status == MemoryStatus.ACTIVE
    for dup in ("memv_r2", "memv_r3"):
        assert by_id[dup].version.status == MemoryStatus.SUPERSEDED
        assert by_id[dup].version.superseded_by_version_id == "memv_r1"
        assert by_id[dup].version.valid_until == NOW


async def test_merge_duplicates_preserves_distinct_facts() -> None:
    npm = _mem("memv_npm", subject="atlas", key="pm", vector=[1.0, 0.0], confidence=0.8)
    pnpm = _mem("memv_pnpm", subject="atlas", key="pm2", vector=[0.0, 1.0], confidence=0.8)
    store = MemoryStoreStub(memories=[npm, pnpm])
    service = SessionConsolidationService(
        store=store,
        write=None,  # type: ignore[arg-type]
        completion_provider=None,  # type: ignore[arg-type]
        embedding_provider=None,  # type: ignore[arg-type]
    )
    scope = Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas")

    superseded = await service.merge_duplicates(scope=scope, now=NOW)

    # Contradictory / distinct facts are never merged; they stay for the contest path.
    assert superseded == 0
    assert all(memory.version.status == MemoryStatus.ACTIVE for memory in store.memories)
