from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def check_database_connectivity(database_url: str) -> None:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
    finally:
        await engine.dispose()
