from copy import deepcopy
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.enums import JobStatus, JobType
from memrise.core.models import BackgroundJob
from memrise.core.time import utc_now
from memrise.integrations.postgres.mappers import job_from_row
from memrise.integrations.postgres.models import JobRow
from memrise.integrations.postgres.session import session_scope
from memrise.ports.ids import IdGenerator


class PostgresJobQueue:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        id_generator: IdGenerator,
    ) -> None:
        self._session_factory = session_factory
        self._ids = id_generator

    async def enqueue(
        self,
        *,
        job_type: JobType,
        payload: dict[str, object],
        dedupe_key: str | None = None,
    ) -> str:
        async with session_scope(self._session_factory) as session:
            now = utc_now()
            job_id = self._ids.new_id("job")
            if dedupe_key:
                job_values: dict[str, object] = {
                    "id": job_id,
                    "type": job_type.value,
                    "payload": deepcopy(payload),
                    "status": JobStatus.PENDING.value,
                    "attempts": 0,
                    "max_attempts": 3,
                    "run_at": now,
                    "locked_at": None,
                    "locked_by": None,
                    "last_error": None,
                    "dedupe_key": dedupe_key,
                    "created_at": now,
                    "updated_at": now,
                }
                inserted_id = await session.scalar(
                    insert(JobRow)
                    .values(job_values)
                    .on_conflict_do_nothing(index_elements=["dedupe_key"])
                    .returning(JobRow.id)
                )
                if inserted_id is not None:
                    return inserted_id
                existing = await session.scalar(
                    select(JobRow.id).where(JobRow.dedupe_key == dedupe_key)
                )
                if existing is None:
                    msg = f"job dedupe conflict could not be resolved for key {dedupe_key!r}"
                    raise RuntimeError(msg)
                return existing

            row = JobRow(
                id=job_id,
                type=job_type.value,
                payload=deepcopy(payload),
                status=JobStatus.PENDING.value,
                attempts=0,
                max_attempts=3,
                run_at=now,
                locked_at=None,
                locked_by=None,
                last_error=None,
                dedupe_key=None,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            return row.id

    async def claim_next(self, *, worker_id: str) -> BackgroundJob | None:
        async with session_scope(self._session_factory) as session:
            now = utc_now()
            row = (
                await session.scalars(
                    select(JobRow)
                    .where(
                        JobRow.status.in_([JobStatus.PENDING.value, JobStatus.RETRYABLE.value]),
                        JobRow.run_at <= now,
                    )
                    .order_by(JobRow.run_at, JobRow.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
            ).first()
            if row is None:
                return None
            row.status = JobStatus.RUNNING.value
            row.attempts += 1
            row.locked_by = worker_id
            row.locked_at = now
            row.updated_at = now
            return job_from_row(row)

    async def get_job(self, job_id: str) -> BackgroundJob | None:
        async with self._session_factory() as session:
            row = await session.get(JobRow, job_id)
            return job_from_row(row) if row is not None else None

    async def find_job_id_by_dedupe_key(self, dedupe_key: str) -> str | None:
        async with self._session_factory() as session:
            return await session.scalar(select(JobRow.id).where(JobRow.dedupe_key == dedupe_key))

    async def complete(self, job_id: str) -> None:
        async with session_scope(self._session_factory) as session:
            row = await session.get(JobRow, job_id)
            if row is None:
                return
            row.status = JobStatus.COMPLETED.value
            row.locked_by = None
            row.locked_at = None
            row.updated_at = utc_now()

    async def fail(self, job_id: str, error: str) -> None:
        async with session_scope(self._session_factory) as session:
            row = await session.get(JobRow, job_id)
            if row is None:
                return
            now = utc_now()
            row.status = (
                JobStatus.FAILED.value
                if row.attempts >= row.max_attempts
                else JobStatus.RETRYABLE.value
            )
            row.locked_by = None
            row.locked_at = None
            row.last_error = error[:4000]
            row.run_at = now + timedelta(seconds=2 ** max(0, row.attempts - 1))
            row.updated_at = now
