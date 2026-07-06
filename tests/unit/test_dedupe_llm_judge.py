from datetime import UTC, datetime

from memrise.consolidation.dedupe import MemoryDedupeService
from memrise.consolidation.duplicates import (
    clusters_from_confirmed_pairs,
    find_duplicate_candidate_pairs,
)
from memrise.core.enums import MemoryStatus
from tests.mocks.memory_store import MemoryStoreStub, make_memory
from tests.mocks.providers import MockCompletionProvider

NOW = datetime(2026, 7, 6, tzinfo=UTC)
MODEL = "mock-embedding"


def _mem(vid, *, subject, key, vector, confidence=0.9):  # type: ignore[no-untyped-def]
    return make_memory(
        memory_id=f"mem_{vid}",
        version_id=vid,
        subject=subject,
        key=key,
        embedding=vector,
        embedding_model=MODEL,
        confidence=confidence,
    )


def test_candidate_pairs_only_in_uncertain_band() -> None:
    # cos(a,b) ~ 0.6 (in band); cos(a,c) ~ 0.996 (above ceiling -> auto-merge, excluded);
    # cos(a,d) ~ 0.0 (below floor, excluded).
    a = _mem("a", subject="s", key="k1", vector=[1.0, 0.0])
    b = _mem("b", subject="s", key="k2", vector=[0.6, 0.8])  # cos 0.6
    c = _mem("c", subject="s", key="k3", vector=[0.996, 0.09])  # cos ~1.0
    d = _mem("d", subject="s", key="k4", vector=[0.0, 1.0])  # cos 0.0

    pairs = find_duplicate_candidate_pairs([a, b, c, d])
    ids = {(p.left.version.id, p.right.version.id) for p in pairs}
    assert ("a", "b") in ids  # cos 0.6, inside [0.45, 0.85)
    assert ("a", "c") not in ids  # cos ~1.0, above ceiling -> auto-merges instead
    assert ("a", "d") not in ids  # cos 0.0, below floor -> unrelated


def test_clusters_from_confirmed_pairs_builds_components() -> None:
    a = _mem("a", subject="s", key="k1", vector=[1.0, 0.0], confidence=0.95)
    b = _mem("b", subject="s", key="k2", vector=[0.6, 0.8], confidence=0.7)
    c = _mem("c", subject="s", key="k3", vector=[0.5, 0.86], confidence=0.6)
    # a~b and b~c confirmed -> one component {a,b,c}, survivor = strongest (a).
    clusters = clusters_from_confirmed_pairs([a, b, c], {("a", "b"), ("b", "c")})
    assert len(clusters) == 1
    assert clusters[0].survivor.version.id == "a"
    assert {d.version.id for d in clusters[0].duplicates} == {"b", "c"}


async def test_dedupe_service_uses_judge_for_ambiguous_pairs() -> None:
    # Two paraphrases the embedding scores at ~0.6 (in band, below auto-merge).
    rule_a = _mem("rule_a", subject="lockfile", key="rule", vector=[1.0, 0.0], confidence=0.95)
    rule_b = _mem("rule_b", subject="pnpm_lock", key="edit", vector=[0.6, 0.8], confidence=0.7)
    store = MemoryStoreStub(memories=[rule_a, rule_b])
    judge = MockCompletionProvider(
        result=None,  # type: ignore[arg-type]  # extract not called here
        equivalent_pairs={("rule_a", "rule_b")},
    )
    service = MemoryDedupeService(store=store, completion_provider=judge)

    superseded = await service.run(NOW)

    assert superseded == 1
    assert judge.judge_calls, "judge should have been consulted"
    by_id = {m.version.id: m for m in store.memories}
    assert by_id["rule_a"].version.status == MemoryStatus.ACTIVE
    assert by_id["rule_b"].version.status == MemoryStatus.SUPERSEDED
    assert by_id["rule_b"].version.superseded_by_version_id == "rule_a"


async def test_dedupe_service_keeps_pairs_the_judge_rejects() -> None:
    a = _mem("a", subject="x", key="k1", vector=[1.0, 0.0])
    b = _mem("b", subject="y", key="k2", vector=[0.6, 0.8])  # in band but judged distinct
    store = MemoryStoreStub(memories=[a, b])
    judge = MockCompletionProvider(result=None, equivalent_pairs=set())  # type: ignore[arg-type]
    service = MemoryDedupeService(store=store, completion_provider=judge)

    assert await service.run(NOW) == 0
    assert all(m.version.status == MemoryStatus.ACTIVE for m in store.memories)
