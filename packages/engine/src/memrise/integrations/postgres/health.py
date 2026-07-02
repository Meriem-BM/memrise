from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def check_database_connectivity(database_url: str) -> dict[str, str]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
            vector_installed = await connection.scalar(
                text("select exists (select 1 from pg_extension where extname = 'vector')")
            )
            if not vector_installed:
                msg = "required extension vector is not installed"
                raise RuntimeError(msg)
            age_installed = await connection.scalar(
                text("select exists (select 1 from pg_extension where extname = 'age')")
            )
            if not age_installed:
                msg = "required extension age is not installed"
                raise RuntimeError(msg)
            return {
                "database": "ok",
                "vector": "ok",
                "age": "ok",
            }
    finally:
        await engine.dispose()
