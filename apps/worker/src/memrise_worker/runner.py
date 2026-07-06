import asyncio
import logging

from memrise import Memrise
from memrise.core.enums import JobType
from memrise.core.time import utc_now
from memrise.runtime.settings import MemorySettings

LOGGER = logging.getLogger("memrise_worker")


class WorkerRunner:
    def __init__(self, *, memory: Memrise, settings: MemorySettings) -> None:
        self._memory = memory
        self._settings = settings
        self._last_lifecycle_bucket: int | None = None
        self._last_dedupe_bucket: int | None = None

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        LOGGER.info("worker started", extra={"worker_id": self._settings.memrise_worker_id})
        while not stop_event.is_set():
            await self._schedule_lifecycle()
            await self._schedule_dedupe()
            processed = await self.run_once()
            if not processed:
                try:
                    await asyncio.wait_for(
                        stop_event.wait(), timeout=self._settings.memrise_job_poll_seconds
                    )
                except TimeoutError:
                    pass
        LOGGER.info("worker stopped", extra={"worker_id": self._settings.memrise_worker_id})

    async def run_once(self) -> bool:
        job = await self._memory.jobs.claim_next(worker_id=self._settings.memrise_worker_id)
        if job is None:
            return False
        try:
            await self._memory.process_job(job)
            await self._memory.jobs.complete(job.id)
            LOGGER.info("job completed", extra={"job_id": job.id, "job_type": job.type.value})
        except Exception as exc:
            await self._memory.jobs.fail(job.id, str(exc))
            LOGGER.exception("job failed", extra={"job_id": job.id, "job_type": job.type.value})
        return True

    async def _schedule_lifecycle(self) -> None:
        """Enqueue one lifecycle sweep per interval; dedupe makes it multi-worker safe."""
        interval = max(60, self._settings.memrise_lifecycle_interval_seconds)
        bucket = int(utc_now().timestamp()) // interval
        if bucket == self._last_lifecycle_bucket:
            return
        await self._memory.jobs.enqueue(
            job_type=JobType.EXPIRE_MEMORIES,
            payload={},
            dedupe_key=f"lifecycle:{bucket}",
        )
        self._last_lifecycle_bucket = bucket

    async def _schedule_dedupe(self) -> None:
        """Enqueue one duplicate-merge sweep per interval; dedupe key makes it safe."""
        interval = max(60, self._settings.memrise_dedupe_interval_seconds)
        bucket = int(utc_now().timestamp()) // interval
        if bucket == self._last_dedupe_bucket:
            return
        await self._memory.jobs.enqueue(
            job_type=JobType.DEDUPE_MEMORIES,
            payload={},
            dedupe_key=f"dedupe:{bucket}",
        )
        self._last_dedupe_bucket = bucket
