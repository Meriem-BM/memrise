from datetime import UTC, datetime

from memrise.consolidation.dedupe import MemoryDedupeService
from memrise.consolidation.session_consolidation import SessionConsolidationService
from memrise.core.enums import EpisodeKind, JobStatus, JobType
from memrise.core.models import BackgroundJob, Episode
from memrise.learning.lifecycle import LifecycleService
from memrise.runtime.ids import UuidGenerator
from memrise.runtime.job_processor import JobProcessor
from memrise.write.importance import ImportanceGate
from memrise.write.service import WriteService
from tests.mocks.graph_services import build_graph_projection_service
from tests.mocks.memory_store import MemoryStoreStub
from tests.mocks.providers import MockCompletionProvider, MockEmbeddingProvider, no_memory_result


class JobQueueStub:
    async def enqueue(self, **kwargs: object) -> str:
        del kwargs
        return "job-1"

    async def find_job_id_by_dedupe_key(self, dedupe_key: str) -> str | None:
        del dedupe_key
        return None

    async def claim_next(self, *, worker_id: str):
        del worker_id
        return None

    async def get_job(self, job_id: str):
        del job_id
        return None

    async def complete(self, job_id: str) -> None:
        del job_id

    async def fail(self, job_id: str, error: str) -> None:
        del job_id, error


def _processor(store: MemoryStoreStub) -> JobProcessor:
    jobs = JobQueueStub()
    write = WriteService(
        store=store,
        jobs=jobs,
        completion_provider=MockCompletionProvider(result=no_memory_result()),
        embedding_provider=MockEmbeddingProvider(),
        importance_gate=ImportanceGate(),
        id_generator=UuidGenerator(),
    )
    return JobProcessor(
        store=store,
        write=write,
        graph_projection=build_graph_projection_service(),
        session_consolidation=SessionConsolidationService(
            store=store,
            write=write,
            completion_provider=MockCompletionProvider(result=no_memory_result()),
            embedding_provider=MockEmbeddingProvider(),
        ),
        lifecycle=LifecycleService(store=store),
        dedupe=MemoryDedupeService(store=store),
    )


def _job(*, job_type: JobType, payload: dict[str, object]) -> BackgroundJob:
    now = datetime.now(UTC)
    return BackgroundJob(
        id="job_test",
        type=job_type,
        payload=payload,
        status=JobStatus.PENDING,
        attempts=0,
        max_attempts=3,
        run_at=now,
        created_at=now,
        updated_at=now,
    )


async def test_consolidate_session_extracts_each_session_episode() -> None:
    store = MemoryStoreStub()
    episode = Episode(
        id="episode_1",
        namespace_id="ns",
        agent_id="agent",
        session_id="session",
        project_id="atlas",
        kind=EpisodeKind.USER_MESSAGE,
        content="Atlas uses pnpm for dependencies.",
        created_at=datetime.now(UTC),
    )
    await store.save_episode(episode)
    processor = _processor(store)

    await processor.process(
        _job(
            job_type=JobType.CONSOLIDATE_SESSION,
            payload={
                "namespace_id": "ns",
                "agent_id": "agent",
                "session_id": "session",
                "project_id": "atlas",
            },
        )
    )

    stages = await store.list_candidate_stages_for_episode("episode_1")
    assert stages


async def test_expire_memories_job_runs_lifecycle() -> None:
    store = MemoryStoreStub()
    processor = _processor(store)

    await processor.process(_job(job_type=JobType.EXPIRE_MEMORIES, payload={}))
