import os
from collections.abc import AsyncIterator
from typing import Literal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.mocks.memory_store import MemoryStoreStub

from memrise.integrations.postgres.repositories import PostgresMemoryStore
from memrise.integrations.postgres.session import make_session_factory
from memrise.ports.repositories import MemoryStore
from memrise.runtime.ids import UuidGenerator

StoreBackend = Literal["stub", "postgres"]


@pytest.fixture(params=["stub", "postgres"], ids=["stub", "postgres"])
def store_backend(request: pytest.FixtureRequest) -> StoreBackend:
    return request.param  # type: ignore[return-value]


@pytest.fixture
async def memory_store(
    store_backend: StoreBackend,
) -> AsyncIterator[tuple[MemoryStore, StoreBackend, async_sessionmaker[AsyncSession] | None]]:
    if store_backend == "stub":
        yield MemoryStoreStub(), store_backend, None
        return

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for PostgreSQL contract tests")

    session_factory = make_session_factory(database_url)
    store = PostgresMemoryStore(session_factory, id_generator=UuidGenerator())
    yield store, store_backend, session_factory
