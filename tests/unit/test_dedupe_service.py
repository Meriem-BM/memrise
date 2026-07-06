from datetime import UTC, datetime

from memrise.consolidation.dedupe import MemoryDedupeService
from memrise.core.enums import MemoryStatus
from tests.mocks.memory_store import MemoryStoreStub, make_memory

NOW = datetime(2026, 7, 5, tzinfo=UTC)
MODEL = "mock-embedding"


def _mem(vid, *, subject, key, vector, project="atlas", confidence=0.9):  # type: ignore[no-untyped-def]
    return make_memory(
        memory_id=f"mem_{vid}",
        version_id=vid,
        subject=subject,
        key=key,
        project_id=project,
        embedding=vector,
        embedding_model=MODEL,
        confidence=confidence,
    )


async def test_dedupe_service_merges_within_each_scope() -> None:
    store = MemoryStoreStub(
        memories=[
            # scope atlas: two near-duplicates
            _mem("memv_a1", subject="lockfile", key="rule", vector=[1.0, 0.0], confidence=0.95),
            _mem("memv_a2", subject="pnpm_lock", key="edit", vector=[0.99, 0.02], confidence=0.7),
            # scope other: a single memory, nothing to merge
            _mem("memv_b1", subject="pm", key="choice", vector=[0.0, 1.0], project="other"),
        ]
    )
    service = MemoryDedupeService(store=store)

    superseded = await service.run(NOW)

    assert superseded == 1
    by_id = {m.version.id: m for m in store.memories}
    assert by_id["memv_a1"].version.status == MemoryStatus.ACTIVE
    assert by_id["memv_a2"].version.status == MemoryStatus.SUPERSEDED
    assert by_id["memv_a2"].version.superseded_by_version_id == "memv_a1"
    # The other scope is untouched.
    assert by_id["memv_b1"].version.status == MemoryStatus.ACTIVE


async def test_dedupe_service_never_merges_across_scopes() -> None:
    # Identical vectors but different projects must not be merged together.
    store = MemoryStoreStub(
        memories=[
            _mem("memv_x", subject="s", key="k", vector=[1.0, 0.0], project="atlas"),
            _mem("memv_y", subject="s", key="k", vector=[1.0, 0.0], project="orion"),
        ]
    )
    service = MemoryDedupeService(store=store)

    assert await service.run(NOW) == 0
    assert all(m.version.status == MemoryStatus.ACTIVE for m in store.memories)
