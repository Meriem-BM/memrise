from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.enums import Criticality, EpisodeKind, MemoryStatus, MemoryType
from memrise.core.models import Episode, Scope
from memrise.core.time import utc_now
from memrise.integrations.postgres.models import MemoryVersionRow
from memrise.integrations.postgres.session import session_scope
from memrise.ports.providers import ExtractedMemoryCandidate


def contract_scope(*, namespace_id: str | None = None) -> Scope:
    return Scope(
        namespace_id=namespace_id or f"contract-{uuid4().hex}",
        agent_id="agent",
        user_id="user",
        project_id="atlas",
    )


def embedding_vector(*, dimensions: int = 1024) -> list[float]:
    return [0.1] * dimensions


def npm_candidate() -> ExtractedMemoryCandidate:
    return ExtractedMemoryCandidate(
        type=MemoryType.DECISION,
        subject="Atlas",
        key="package_manager",
        content="Atlas uses npm as the package manager.",
        structured_value={"value": "npm"},
        confidence=0.9,
        importance=0.8,
        criticality=Criticality.NORMAL,
        evidence_quote="Atlas uses npm as the package manager.",
    )


def pnpm_candidate() -> ExtractedMemoryCandidate:
    return ExtractedMemoryCandidate(
        type=MemoryType.DECISION,
        subject="Atlas",
        key="package_manager",
        content="Atlas uses pnpm as the package manager.",
        structured_value={"value": "pnpm"},
        confidence=0.9,
        importance=0.8,
        criticality=Criticality.NORMAL,
        evidence_quote="Atlas used npm before, but now uses pnpm.",
    )


def capture_episode(
    *,
    scope: Scope,
    episode_id: str,
    idempotency_key: str | None = "capture-1",
    content: str = "Atlas uses pnpm for dependencies.",
) -> Episode:
    return Episode(
        id=episode_id,
        namespace_id=scope.namespace_id,
        agent_id=scope.agent_id,
        session_id="session",
        project_id=scope.project_id,
        kind=EpisodeKind.USER_MESSAGE,
        content=content,
        created_at=datetime.now(UTC),
        idempotency_key=idempotency_key,
    )


async def seed_active_npm_memory(
    store,
    *,
    scope: Scope,
    source_episode_ids: list[str] | None = None,
) -> str:
    outcome = await store.apply_candidate(
        scope=scope,
        candidate=npm_candidate(),
        source_episode_ids=source_episode_ids or [],
        embedding=embedding_vector(),
    )
    memory = outcome.memory
    assert memory is not None
    return memory.identity.id


async def seed_superseded_npm_only(
    store,
    *,
    scope: Scope,
    backend: str,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> str:
    if backend == "stub":
        from tests.mocks.memory_store import MemoryStoreStub, make_memory

        assert isinstance(store, MemoryStoreStub)
        seeded = make_memory(
            memory_id="mem_package_manager",
            version_id="memv_npm",
            namespace_id=scope.namespace_id,
            agent_id=scope.agent_id,
            user_id=scope.user_id,
            project_id=scope.project_id,
            content="Atlas uses npm as the package manager.",
            structured_value={"value": "npm"},
            status=MemoryStatus.SUPERSEDED,
        )
        store.memories.append(seeded)
        return seeded.identity.id

    memory_id = await seed_active_npm_memory(store, scope=scope)
    assert session_factory is not None
    now = utc_now()
    async with session_scope(session_factory) as session:
        await session.execute(
            update(MemoryVersionRow)
            .where(
                MemoryVersionRow.memory_id == memory_id,
                MemoryVersionRow.status == MemoryStatus.ACTIVE.value,
            )
            .values(
                status=MemoryStatus.SUPERSEDED.value,
                valid_until=now,
                updated_at=now,
            )
        )
    return memory_id


async def seed_superseded_npm_with_active_pnpm(
    store,
    *,
    scope: Scope,
) -> tuple[str, str]:
    first_outcome = await store.apply_candidate(
        scope=scope,
        candidate=npm_candidate(),
        source_episode_ids=[],
        embedding=embedding_vector(),
    )
    first = first_outcome.memory
    assert first is not None

    second_outcome = await store.apply_candidate(
        scope=scope,
        candidate=pnpm_candidate(),
        source_episode_ids=[],
        embedding=embedding_vector(dimensions=1024),
    )
    second = second_outcome.memory
    assert second is not None
    assert second.identity.id == first.identity.id
    return first.version.id, second.version.id
