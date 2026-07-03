import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from tests.integration.db import database_url

from memrise.integrations.apache_age.repository import AgeGraphRepository
from memrise.integrations.postgres.session import make_session_factory
from memrise.runtime.ids import UuidGenerator

pytestmark = pytest.mark.asyncio


class FixedIdGenerator(UuidGenerator):
    def __init__(self, prefix: str = "age-test") -> None:
        self._prefix = prefix
        self._counter = 0

    def new_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{self._prefix}-{prefix}-{self._counter}"


async def test_age_extension_is_installed() -> None:
    engine = create_async_engine(database_url())
    async with engine.connect() as connection:
        installed = await connection.scalar(
            text("select exists (select 1 from pg_extension where extname = 'age')")
        )
        assert installed is True
    await engine.dispose()


async def test_application_tables_live_in_public_schema() -> None:
    engine = create_async_engine(database_url())
    async with engine.connect() as connection:
        misplaced = (
            (
                await connection.execute(
                    text(
                        "select tablename from pg_tables "
                        "where schemaname = 'ag_catalog' "
                        "and tablename in ('episodes', 'memories', 'memory_versions', 'jobs')"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert misplaced == []
        episodes_schema = await connection.scalar(
            text("select table_schema from information_schema.tables where table_name = 'episodes'")
        )
        assert episodes_schema == "public"
    await engine.dispose()


async def test_age_graph_repository_accepts_injected_uuid_generator() -> None:
    session_factory = make_session_factory(database_url())
    id_generator = FixedIdGenerator(prefix="injected")
    repository = AgeGraphRepository(session_factory, id_generator=id_generator)

    assert await repository.is_available() is True
    assert repository.stable_node_uid(
        namespace_id="it-age",
        node_type="Project",
        name="Atlas",
    ).startswith("node-it-age:Project:atlas")
