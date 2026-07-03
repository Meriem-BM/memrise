from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.builders.memory import (
    capture_episode,
    contract_scope,
    embedding_vector,
    npm_candidate,
    pnpm_candidate,
    seed_active_npm_memory,
    seed_superseded_npm_only,
    seed_superseded_npm_with_active_pnpm,
)

from memrise.core.enums import MemoryStatus
from memrise.core.errors import IdempotencyConflictError
from memrise.ports.repositories import MemoryStore

pytestmark = pytest.mark.asyncio


async def test_apply_candidate_supersedes_active_memory_without_deleting_history(
    memory_store: tuple[MemoryStore, str, async_sessionmaker[AsyncSession] | None],
) -> None:
    store, _backend, _session_factory = memory_store
    scope = contract_scope()

    await seed_active_npm_memory(store, scope=scope)

    outcome = await store.apply_candidate(
        scope=scope,
        candidate=pnpm_candidate(),
        source_episode_ids=[],
        embedding=embedding_vector(),
    )
    created = outcome.memory

    assert created is not None
    history = await store.list_memory_history(created.identity.id)
    assert len(history) == 2
    old_versions = [
        memory for memory in history if memory.version.status == MemoryStatus.SUPERSEDED
    ]
    assert len(old_versions) == 1
    old = old_versions[0]
    assert old.version.valid_until is not None
    assert old.version.superseded_by_version_id == created.version.id
    assert created.version.status == MemoryStatus.ACTIVE
    assert created.version.supersedes_version_id == old.version.id


async def test_apply_candidate_does_not_recreate_superseded_duplicate(
    memory_store: tuple[MemoryStore, str, async_sessionmaker[AsyncSession] | None],
) -> None:
    store, backend, session_factory = memory_store
    scope = contract_scope()

    memory_id = await seed_superseded_npm_only(
        store,
        scope=scope,
        backend=backend,
        session_factory=session_factory,
    )

    outcome = await store.apply_candidate(
        scope=scope,
        candidate=npm_candidate(),
        source_episode_ids=[],
        embedding=embedding_vector(),
    )

    assert outcome.memory is None
    assert outcome.skip_reason is not None
    history = await store.list_memory_history(memory_id)
    assert len(history) == 1
    assert history[0].version.status == MemoryStatus.SUPERSEDED


async def test_apply_candidate_drops_repeated_historical_value_when_newer_value_is_active(
    memory_store: tuple[MemoryStore, str, async_sessionmaker[AsyncSession] | None],
) -> None:
    store, _backend, _session_factory = memory_store
    scope = contract_scope()

    _npm_version_id, pnpm_version_id = await seed_superseded_npm_with_active_pnpm(
        store,
        scope=scope,
    )

    outcome = await store.apply_candidate(
        scope=scope,
        candidate=npm_candidate(),
        source_episode_ids=[],
        embedding=embedding_vector(),
    )

    assert outcome.memory is None
    assert outcome.skip_reason == "reconcile:historical_duplicate"
    active = await store.find_current_memory(
        scope=scope,
        subject="Atlas",
        key="package_manager",
    )
    assert active is not None
    assert active.version.id == pnpm_version_id


async def test_save_episode_replays_idempotency_key(
    memory_store: tuple[MemoryStore, str, async_sessionmaker[AsyncSession] | None],
) -> None:
    store, _backend, _session_factory = memory_store
    scope = contract_scope()

    first = capture_episode(scope=scope, episode_id=f"episode_{uuid4().hex}")
    second = capture_episode(scope=scope, episode_id=f"episode_{uuid4().hex}")

    first_outcome = await store.save_episode(first)
    second_outcome = await store.save_episode(second)

    assert first_outcome.created is True
    assert second_outcome.created is False
    assert first_outcome.episode.id == second_outcome.episode.id
    assert first_outcome.episode.id == first.id


async def test_save_episode_rejects_idempotency_key_payload_mismatch(
    memory_store: tuple[MemoryStore, str, async_sessionmaker[AsyncSession] | None],
) -> None:
    store, _backend, _session_factory = memory_store
    scope = contract_scope()

    await store.save_episode(capture_episode(scope=scope, episode_id=f"episode_{uuid4().hex}"))
    mismatched = capture_episode(
        scope=scope,
        episode_id=f"episode_{uuid4().hex}",
        content="Different payload.",
    )

    with pytest.raises(IdempotencyConflictError):
        await store.save_episode(mismatched)
