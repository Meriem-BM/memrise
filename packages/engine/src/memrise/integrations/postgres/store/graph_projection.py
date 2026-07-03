from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.enums import JobStatus, JobType, MemoryStatus
from memrise.core.models import CanonicalMemory
from memrise.core.time import utc_now
from memrise.integrations.postgres.schema.models import GraphProjectionJobRow, JobRow
from memrise.integrations.postgres.session import session_scope
from memrise.ports.ids import IdGenerator
from memrise.ports.providers import ExtractedGraphRelation


class PostgresGraphProjectionRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        id_generator: IdGenerator,
    ) -> None:
        self._session_factory = session_factory
        self._ids = id_generator

    async def schedule_graph_projection(
        self,
        *,
        memory: CanonicalMemory,
        relations: list[ExtractedGraphRelation],
    ) -> str | None:
        if memory.version.status != MemoryStatus.ACTIVE or not relations:
            return None
        dedupe_key = f"graph-projection:{memory.version.id}"
        async with session_scope(self._session_factory) as session:
            existing_job = (
                await session.scalars(select(JobRow).where(JobRow.dedupe_key == dedupe_key))
            ).first()
            if existing_job is not None:
                return existing_job.id
            now = utc_now()
            job_id = self._ids.new_id("job")
            session.add(
                JobRow(
                    id=job_id,
                    type=JobType.PROJECT_GRAPH.value,
                    payload={
                        "memory_version_id": memory.version.id,
                        "namespace_id": memory.identity.namespace_id,
                        "relations": [relation.model_dump() for relation in relations],
                    },
                    status=JobStatus.PENDING.value,
                    attempts=0,
                    max_attempts=5,
                    run_at=now,
                    dedupe_key=dedupe_key,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                GraphProjectionJobRow(
                    id=self._ids.new_id("gproj"),
                    namespace_id=memory.identity.namespace_id,
                    memory_version_id=memory.version.id,
                    status="pending",
                    attempts=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            return job_id
