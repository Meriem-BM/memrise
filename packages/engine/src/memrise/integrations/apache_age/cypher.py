import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.integrations.apache_age.connection import prepare_age_session


class CypherExecutor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        graph_name: str,
        query_timeout_ms: int,
    ) -> None:
        self._session_factory = session_factory
        self._graph_name = graph_name
        self._query_timeout_ms = query_timeout_ms

    async def run(
        self,
        query_template: str,
        parameters: dict[str, object],
        *,
        columns: tuple[str, ...],
    ) -> list[dict[str, object]]:
        params_json = json.dumps(parameters)
        column_defs = ", ".join(f"{name} agtype" for name in columns)
        sql = (
            f"SELECT * FROM cypher('{self._graph_name}', $${query_template}$$, "
            f"cast(:params as agtype)) as ({column_defs})"
        )
        async with self._session_factory() as session, session.begin():
            await prepare_age_session(session)
            await session.execute(
                text(f"SET LOCAL statement_timeout = '{self._query_timeout_ms}ms'")
            )
            result = await session.execute(text(sql), {"params": params_json})
            return [dict(row) for row in result.mappings().all()]
