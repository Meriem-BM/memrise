from datetime import UTC, datetime

from tests.mocks.memory_store import MemoryStoreStub, make_memory
from tests.mocks.providers import (
    MockCompletionProvider,
    MockEmbeddingProvider,
    no_memory_result,
    single_candidate_result,
)

from memrise.core.enums import CandidateStageStatus, Criticality, EpisodeKind, JobType, MemoryType
from memrise.core.models import BackgroundJob, Episode, Scope
from memrise.ports.providers import EmbeddingVector, ExtractedMemoryCandidate
from memrise.runtime.ids import UuidGenerator
from memrise.write.importance import ImportanceGate
from memrise.write.service import WriteService


class JobQueueStub:
    async def enqueue(
        self,
        *,
        job_type: JobType,
        payload: dict[str, object],
        dedupe_key: str | None = None,
    ) -> str:
        del job_type, payload, dedupe_key
        return "job_test"

    async def find_job_id_by_dedupe_key(self, dedupe_key: str) -> str | None:
        del dedupe_key
        return None

    async def claim_next(self, *, worker_id: str) -> BackgroundJob | None:
        del worker_id
        return None

    async def get_job(self, job_id: str) -> BackgroundJob | None:
        del job_id
        return None

    async def complete(self, job_id: str) -> None:
        del job_id

    async def fail(self, job_id: str, error: str) -> None:
        del job_id, error


def _episode(content: str) -> Episode:
    return Episode(
        id="episode_test",
        namespace_id="ns",
        agent_id="agent",
        session_id="session",
        project_id="atlas",
        kind=EpisodeKind.USER_MESSAGE,
        content=content,
        created_at=datetime.now(UTC),
    )


def _service(store: MemoryStoreStub, completion: MockCompletionProvider) -> WriteService:
    return WriteService(
        store=store,
        jobs=JobQueueStub(),
        completion_provider=completion,
        embedding_provider=MockEmbeddingProvider(),
        importance_gate=ImportanceGate(),
        id_generator=UuidGenerator(),
    )


async def test_extract_episode_stages_and_promotes_candidate() -> None:
    episode = _episode("Atlas used npm before, but now it uses pnpm.")
    store = MemoryStoreStub()
    await store.save_episode(episode)
    completion = MockCompletionProvider(
        result=single_candidate_result(
            ExtractedMemoryCandidate(
                type=MemoryType.DECISION,
                subject="Atlas",
                key="package_manager",
                content="Atlas uses pnpm as its package manager.",
                structured_value={"value": "pnpm"},
                confidence=0.9,
                importance=0.8,
                criticality=Criticality.NORMAL,
                evidence_quote="Atlas used npm before, but now it uses pnpm.",
            )
        )
    )

    outcome = await _service(store, completion).extract_episode(episode.id, datetime.now(UTC))

    assert outcome.created_memory_version_ids
    stage = next(iter(store.candidate_stages.values()))
    assert stage.status == CandidateStageStatus.PROMOTED
    assert stage.memory_version_id == outcome.created_memory_version_ids[0]
    assert stage.promotion_score > 0


async def test_extract_episode_stages_rejected_classification() -> None:
    episode = _episode("Thanks, that is all.")
    store = MemoryStoreStub()
    await store.save_episode(episode)
    completion = MockCompletionProvider(result=no_memory_result())

    outcome = await _service(store, completion).extract_episode(episode.id, datetime.now(UTC))

    assert outcome.created_memory_version_ids == []
    stage = next(iter(store.candidate_stages.values()))
    assert stage.status == CandidateStageStatus.REJECTED
    assert stage.rejection_reason == "classification:no_extract"


async def test_extract_episode_retry_skips_llm_when_stages_exist() -> None:
    episode = _episode("Atlas used npm before, but now it uses pnpm.")
    store = MemoryStoreStub()
    await store.save_episode(episode)
    completion = MockCompletionProvider(
        result=single_candidate_result(
            ExtractedMemoryCandidate(
                type=MemoryType.DECISION,
                subject="Atlas",
                key="package_manager",
                content="Atlas uses pnpm as its package manager.",
                structured_value={"value": "pnpm"},
                confidence=0.9,
                importance=0.8,
                criticality=Criticality.NORMAL,
                evidence_quote="Atlas used npm before, but now it uses pnpm.",
            )
        )
    )
    service = _service(store, completion)

    first = await service.extract_episode(episode.id, datetime.now(UTC))
    call_count_after_first = len(completion.captured)
    second = await service.extract_episode(episode.id, datetime.now(UTC))

    assert len(completion.captured) == call_count_after_first
    assert second.created_memory_version_ids == first.created_memory_version_ids
    stage = next(iter(store.candidate_stages.values()))
    assert stage.status == CandidateStageStatus.PROMOTED


async def test_apply_candidate_reinforces_semantic_duplicate_under_different_key() -> None:
    existing = make_memory(
        memory_id="mem_pm",
        version_id="memv_pm",
        key="package_manager",
        content="Atlas uses pnpm as the package manager.",
        embedding=[1.0, 0.0, 0.0],
    )
    store = MemoryStoreStub(memories=[existing])
    candidate = ExtractedMemoryCandidate(
        type=MemoryType.DECISION,
        subject="Atlas",
        key="preferred_package_manager",
        content="pnpm is the preferred package manager for Atlas.",
        confidence=0.9,
        importance=0.8,
        criticality=Criticality.NORMAL,
        evidence_quote="pnpm is the preferred package manager for Atlas.",
    )

    outcome = await store.apply_candidate(
        scope=Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas"),
        candidate=candidate,
        source_episode_ids=["ep_1"],
        embedding=EmbeddingVector(values=[1.0, 0.0, 0.05], model="mock-embedding", dimensions=3),
    )

    assert outcome.memory is not None
    assert outcome.memory.identity.id == "mem_pm"
    assert len({memory.identity.id for memory in store.memories}) == 1


async def test_apply_candidate_adds_new_memory_when_not_semantically_similar() -> None:
    existing = make_memory(
        memory_id="mem_pm",
        version_id="memv_pm",
        key="package_manager",
        content="Atlas uses pnpm as the package manager.",
        embedding=[1.0, 0.0, 0.0],
    )
    store = MemoryStoreStub(memories=[existing])
    candidate = ExtractedMemoryCandidate(
        type=MemoryType.FACT,
        subject="Atlas",
        key="deploy_day",
        content="Atlas deploys on Fridays.",
        confidence=0.9,
        importance=0.8,
        criticality=Criticality.NORMAL,
        evidence_quote="Atlas deploys on Fridays.",
    )

    outcome = await store.apply_candidate(
        scope=Scope(namespace_id="ns", agent_id="agent", user_id="user", project_id="atlas"),
        candidate=candidate,
        source_episode_ids=["ep_1"],
        embedding=EmbeddingVector(values=[0.0, 1.0, 0.0], model="mock-embedding", dimensions=3),
    )

    assert outcome.memory is not None
    assert outcome.memory.identity.id != "mem_pm"
    assert len({memory.identity.id for memory in store.memories}) == 2
