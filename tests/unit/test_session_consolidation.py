from datetime import UTC, datetime

from memrise.consolidation.session_consolidation import SessionConsolidationService
from memrise.core.enums import Criticality, EpisodeKind, MemoryType
from memrise.core.models import Episode
from memrise.ports.providers import ConsolidationResult, ExtractedMemoryCandidate
from memrise.runtime.ids import UuidGenerator
from memrise.schemas.requests import ConsolidateRequest
from memrise.write.importance import ImportanceGate
from memrise.write.service import WriteService
from tests.mocks.memory_store import MemoryStoreStub, make_memory
from tests.mocks.providers import (
    MockCompletionProvider,
    MockEmbeddingProvider,
    no_memory_result,
)

NOW = datetime(2026, 7, 3, tzinfo=UTC)


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


def _episode(episode_id: str, content: str) -> Episode:
    return Episode(
        id=episode_id,
        namespace_id="ns",
        agent_id="agent",
        user_id="user",
        session_id="session-1",
        project_id="atlas",
        kind=EpisodeKind.USER_MESSAGE,
        content=content,
        created_at=NOW,
    )


def _candidate(
    *, content: str, evidence_quote: str, key: str = "deploy_lesson"
) -> ExtractedMemoryCandidate:
    return ExtractedMemoryCandidate(
        type=MemoryType.LESSON,
        subject="Atlas",
        key=key,
        content=content,
        confidence=0.9,
        importance=0.8,
        criticality=Criticality.NORMAL,
        evidence_quote=evidence_quote,
    )


def _service(
    store: MemoryStoreStub, provider: MockCompletionProvider
) -> SessionConsolidationService:
    embedding_provider = MockEmbeddingProvider()
    write = WriteService(
        store=store,
        jobs=JobQueueStub(),
        completion_provider=provider,
        embedding_provider=embedding_provider,
        importance_gate=ImportanceGate(),
        id_generator=UuidGenerator(),
    )
    return SessionConsolidationService(
        store=store,
        write=write,
        completion_provider=provider,
        embedding_provider=embedding_provider,
    )


def _request() -> ConsolidateRequest:
    return ConsolidateRequest(
        namespace_id="ns",
        agent_id="agent",
        session_id="session-1",
        user_id="user",
        project_id="atlas",
    )


async def test_consolidation_applies_synthesized_candidate() -> None:
    store = MemoryStoreStub()
    episode_a = _episode("ep_1", "Deploy failed because the cache was stale.")
    episode_b = _episode("ep_2", "Clearing the cache before deploy fixed it.")
    store.episodes = {episode.id: episode for episode in (episode_a, episode_b)}
    provider = MockCompletionProvider(
        result=no_memory_result(),
        consolidation=ConsolidationResult(
            candidates=[
                _candidate(
                    content="Clear the cache before deploying Atlas.",
                    evidence_quote="Clearing the cache before deploy fixed it.",
                )
            ],
            model_name="mock",
            prompt_version="consolidation_v1",
        ),
    )

    await _service(store, provider).consolidate_session(_request(), NOW)

    assert provider.consolidation_calls, "consolidation model was not invoked"
    contents = [memory.version.content for memory in store.memories]
    assert "Clear the cache before deploying Atlas." in contents


async def test_consolidation_rejects_candidate_without_session_evidence() -> None:
    store = MemoryStoreStub()
    episode = _episode("ep_1", "Deploy failed because the cache was stale.")
    store.episodes = {episode.id: episode}
    provider = MockCompletionProvider(
        result=no_memory_result(),
        consolidation=ConsolidationResult(
            candidates=[
                _candidate(
                    content="Atlas requires Kubernetes 1.30.",
                    evidence_quote="Atlas requires Kubernetes 1.30.",
                )
            ],
            model_name="mock",
            prompt_version="consolidation_v1",
        ),
    )

    await _service(store, provider).consolidate_session(_request(), NOW)

    assert store.memories == []


async def test_consolidation_passes_existing_memories_to_model() -> None:
    store = MemoryStoreStub(memories=[make_memory()])
    episode = _episode("ep_1", "Deploy failed because the cache was stale.")
    store.episodes = {episode.id: episode}
    provider = MockCompletionProvider(result=no_memory_result())

    await _service(store, provider).consolidate_session(_request(), NOW)

    call = provider.consolidation_calls[0]
    existing = call["existing_memories"]
    assert isinstance(existing, list) and len(existing) == 1
