from datetime import UTC, datetime, timedelta

import pytest

from memrise.core.enums import MemoryStatus
from memrise.learning.lifecycle import (
    CONTESTED_RESOLUTION_MARGIN,
    LifecycleService,
    decayed_usefulness,
)
from tests.mocks.memory_store import MemoryStoreStub, make_memory

NOW = datetime(2026, 7, 3, tzinfo=UTC)


def test_decayed_usefulness_moves_toward_neutral() -> None:
    one_half_life = decayed_usefulness(1.0, elapsed_seconds=30 * 86_400, half_life_days=30)
    assert one_half_life == pytest.approx(0.75)

    low = decayed_usefulness(0.1, elapsed_seconds=30 * 86_400, half_life_days=30)
    assert low == pytest.approx(0.3)

    assert decayed_usefulness(0.9, elapsed_seconds=0, half_life_days=30) == 0.9


async def test_lifecycle_expires_due_memory_versions() -> None:
    store = MemoryStoreStub(
        memories=[
            make_memory(
                version_id="memv_due",
                valid_until=NOW - timedelta(days=1),
            ),
            make_memory(memory_id="mem_live", version_id="memv_live", key="other"),
        ]
    )

    result = await LifecycleService(store=store).run(NOW + timedelta(days=1))

    assert result.expired_memory_versions == 1
    statuses = {memory.version.id: memory.version.status for memory in store.memories}
    assert statuses["memv_due"] == MemoryStatus.EXPIRED
    assert statuses["memv_live"] == MemoryStatus.ACTIVE


async def test_lifecycle_decays_usefulness_toward_neutral() -> None:
    store = MemoryStoreStub(memories=[make_memory(version_id="memv_hot", usefulness_score=0.9)])

    result = await LifecycleService(store=store, half_life_days=30).run(NOW + timedelta(days=365))

    assert result.decayed_versions == 1
    decayed = store.memories[0].version.usefulness_score
    assert 0.5 < decayed < 0.9


async def test_lifecycle_resolves_contested_pair_with_clear_winner() -> None:
    loser = make_memory(
        memory_id="mem_pm",
        version_id="memv_old",
        status=MemoryStatus.CONTESTED,
        usefulness_score=0.3,
        confidence=0.5,
        version_number=1,
    )
    winner = make_memory(
        memory_id="mem_pm",
        version_id="memv_new",
        status=MemoryStatus.CONTESTED,
        usefulness_score=0.3 + CONTESTED_RESOLUTION_MARGIN,
        confidence=0.5 + CONTESTED_RESOLUTION_MARGIN,
        version_number=2,
    )
    store = MemoryStoreStub(memories=[loser, winner])

    result = await LifecycleService(store=store).run(NOW)

    assert result.resolved_contested == 1
    by_id = {memory.version.id: memory.version for memory in store.memories}
    assert by_id["memv_new"].status == MemoryStatus.ACTIVE
    assert by_id["memv_old"].status == MemoryStatus.SUPERSEDED
    assert by_id["memv_old"].superseded_by_version_id == "memv_new"


async def test_lifecycle_leaves_close_contested_pairs_alone() -> None:
    store = MemoryStoreStub(
        memories=[
            make_memory(
                memory_id="mem_pm",
                version_id="memv_a",
                status=MemoryStatus.CONTESTED,
                usefulness_score=0.5,
                version_number=1,
            ),
            make_memory(
                memory_id="mem_pm",
                version_id="memv_b",
                status=MemoryStatus.CONTESTED,
                usefulness_score=0.55,
                version_number=2,
            ),
        ]
    )

    result = await LifecycleService(store=store).run(NOW)

    assert result.resolved_contested == 0
    assert all(memory.version.status == MemoryStatus.CONTESTED for memory in store.memories)
