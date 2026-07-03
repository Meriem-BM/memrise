from memrise.consolidation.graph_projection import GraphProjectionService
from memrise.consolidation.session_consolidation import SessionConsolidationService
from memrise.core.enums import JobType
from memrise.core.errors import UnimplementedJobError
from memrise.core.models import BackgroundJob
from memrise.core.time import utc_now
from memrise.ports.providers import ExtractedGraphRelation
from memrise.ports.repositories import JobQueue, MemoryStore
from memrise.schemas.requests import ConsolidateRequest
from memrise.write.service import WriteService


class JobProcessor:
    def __init__(
        self,
        *,
        store: MemoryStore,
        write: WriteService,
        graph_projection: GraphProjectionService,
        session_consolidation: SessionConsolidationService,
    ) -> None:
        self._store = store
        self._write = write
        self._graph_projection = graph_projection
        self._session_consolidation = session_consolidation

    async def process(self, job: BackgroundJob) -> None:
        if job.type == JobType.EXTRACT_EPISODE:
            episode_id = str(job.payload["episode_id"])
            await self._write.extract_episode(episode_id, utc_now())
            return
        if job.type == JobType.PROJECT_GRAPH:
            memory_version_id = str(job.payload["memory_version_id"])
            memory = await self._store.get_memory_version_by_id(memory_version_id)
            if memory is None:
                msg = f"memory version {memory_version_id!r} not found for graph projection"
                raise RuntimeError(msg)
            relations = [
                ExtractedGraphRelation.model_validate(raw)
                for raw in job.payload.get("relations", [])
            ]
            await self._graph_projection.project_memory(memory=memory, relations=relations)
            return
        if job.type == JobType.CONSOLIDATE_SESSION:
            request = ConsolidateRequest.model_validate(job.payload)
            await self._session_consolidation.consolidate_session(request, utc_now())
            return
        if job.type in {JobType.EXPIRE_MEMORIES, JobType.PROCESS_FEEDBACK}:
            raise UnimplementedJobError(job.type)
        raise UnimplementedJobError(job.type)

    async def process_once(self, jobs: JobQueue, *, worker_id: str) -> bool:
        job = await jobs.claim_next(worker_id=worker_id)
        if job is None:
            return False
        try:
            await self.process(job)
            await jobs.complete(job.id)
        except Exception as exc:
            await jobs.fail(job.id, str(exc))
            raise
        return True
