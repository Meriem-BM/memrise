import asyncio
import logging
from collections.abc import Awaitable, Callable

from memrise import Memory
from memrise.core.enums import JobType
from memrise.core.models import BackgroundJob
from memrise.runtime.settings import MemorySettings
from memrise_worker.handlers.consolidate_session import handle_consolidate_session
from memrise_worker.handlers.expire_memories import handle_expire_memories
from memrise_worker.handlers.extract_episode import handle_extract_episode
from memrise_worker.handlers.process_feedback import handle_process_feedback

LOGGER = logging.getLogger("memrise_worker")

Handler = Callable[[Memory, BackgroundJob], Awaitable[None]]


class WorkerRunner:
    def __init__(self, *, memory: Memory, settings: MemorySettings) -> None:
        self._memory = memory
        self._settings = settings
        self._handlers = {
            JobType.EXTRACT_EPISODE: handle_extract_episode,
            JobType.CONSOLIDATE_SESSION: handle_consolidate_session,
            JobType.EXPIRE_MEMORIES: handle_expire_memories,
            JobType.PROCESS_FEEDBACK: handle_process_feedback,
        }

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        LOGGER.info("worker started", extra={"worker_id": self._settings.memrise_worker_id})
        while not stop_event.is_set():
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
            handler = self._handlers[job.type]
            await handler(self._memory, job)
            await self._memory.jobs.complete(job.id)
            LOGGER.info("job completed", extra={"job_id": job.id, "job_type": job.type.value})
        except Exception as exc:
            await self._memory.jobs.fail(job.id, str(exc))
            LOGGER.exception("job failed", extra={"job_id": job.id, "job_type": job.type.value})
        return True
