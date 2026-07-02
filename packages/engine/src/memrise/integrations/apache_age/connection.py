from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

_AGE_SEARCH_PATH = 'ag_catalog, "$user", public'


async def prepare_age_session(session: AsyncSession) -> None:
    await session.execute(text("LOAD 'age'"))
    await session.execute(text(f"SET search_path = {_AGE_SEARCH_PATH}"))


def register_age_session_initializer(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("LOAD 'age'")
        cursor.execute(f"SET search_path = {_AGE_SEARCH_PATH}")
        cursor.close()
