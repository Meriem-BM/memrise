from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from memrise.core.enums import EpisodeKind, JobType
from memrise.core.models import Episode
from memrise.runtime.ids import UuidGenerator
from memrise.schemas.requests import CaptureRequest
from memrise.write.importance import ImportanceGate
from memrise.write.service import WriteService
from tests.mocks.memory_store import MemoryStoreStub
from tests.mocks.providers import MockCompletionProvider, MockEmbeddingProvider, no_memory_result


class DedupingJobQueueStub:
    def __init__(self) -> None:
        self.jobs: dict[str, str] = {}

    async def enqueue(
        self,
        *,
        job_type: JobType,
        payload: dict[str, object],
        dedupe_key: str | None = None,
    ) -> str:
        del job_type, payload
        if dedupe_key and dedupe_key in self.jobs:
            return self.jobs[dedupe_key]
        job_id = f"job-{len(self.jobs) + 1}"
        if dedupe_key:
            self.jobs[dedupe_key] = job_id
        return job_id

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

    async def find_job_id_by_dedupe_key(self, dedupe_key: str) -> str | None:
        return self.jobs.get(dedupe_key)


def _episode(
    *, episode_id: str = "episode_a", idempotency_key: str | None = "capture-1"
) -> Episode:
    return Episode(
        id=episode_id,
        namespace_id="ns",
        agent_id="agent",
        session_id="session",
        project_id="atlas",
        kind=EpisodeKind.USER_MESSAGE,
        content="Atlas uses pnpm for dependencies.",
        created_at=datetime.now(UTC),
        idempotency_key=idempotency_key,
    )


def _write_service(store: MemoryStoreStub, jobs: DedupingJobQueueStub) -> WriteService:
    return WriteService(
        store=store,
        jobs=jobs,
        completion_provider=MockCompletionProvider(result=no_memory_result()),
        embedding_provider=MockEmbeddingProvider(),
        importance_gate=ImportanceGate(),
        id_generator=UuidGenerator(),
    )


def test_capture_request_requires_single_event_for_idempotency_key() -> None:
    with pytest.raises(ValidationError, match="idempotency_key requires exactly one capture event"):
        CaptureRequest.model_validate(
            {
                "namespace_id": "ns",
                "agent_id": "agent",
                "session_id": "session",
                "idempotency_key": "capture-1",
                "events": [
                    {"kind": "user_message", "content": "one"},
                    {"kind": "user_message", "content": "two"},
                ],
            }
        )


async def test_capture_episode_replays_existing_episode_and_job() -> None:
    store = MemoryStoreStub()
    jobs = DedupingJobQueueStub()
    service = _write_service(store, jobs)

    first_episode, first_job = await service.capture_episode(_episode())
    second_episode, second_job = await service.capture_episode(_episode(episode_id="episode_b"))

    assert first_episode.id == second_episode.id
    assert first_job == second_job
    assert len(store.episodes) == 1
    assert len(jobs.jobs) == 1
