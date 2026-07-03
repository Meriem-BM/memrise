import asyncio
from uuid import uuid4

import pytest
from tests.integration.db import database_url
from tests.mocks.graph_repository import GraphRepositoryStub
from tests.mocks.graph_services import build_graph_projection_service
from tests.mocks.providers import (
    MockCompletionProvider,
    MockEmbeddingProvider,
    single_candidate_result,
)

from memrise.core.enums import Criticality, EpisodeKind, MemoryStatus, MemoryType
from memrise.core.models import Scope
from memrise.integrations.postgres import (
    PostgresJobQueue,
    PostgresMemoryStore,
    make_session_factory,
)
from memrise.learning.policy import DefaultFeedbackPolicy
from memrise.ports.providers import EmbeddingVector, ExtractedMemoryCandidate
from memrise.runtime.ids import UuidGenerator
from memrise.runtime.memory import Memrise
from memrise.runtime.token_counter import ApproximateTokenCounter

pytestmark = pytest.mark.asyncio

DEMO_EPISODE = (
    "Atlas used npm before, but we now use pnpm. Never edit its generated lockfile manually."
)


def build_mock_memory() -> tuple[Memrise, MockCompletionProvider]:
    url = database_url()
    session_factory = make_session_factory(url)
    id_generator = UuidGenerator()
    store = PostgresMemoryStore(session_factory, id_generator=id_generator)
    jobs = PostgresJobQueue(session_factory, id_generator=id_generator)
    completion = MockCompletionProvider(
        result=single_candidate_result(
            ExtractedMemoryCandidate(
                type=MemoryType.FACT,
                subject="Atlas",
                key="package_manager",
                content="Atlas uses pnpm for dependencies.",
                structured_value={},
                confidence=0.9,
                importance=0.8,
                criticality=Criticality.NORMAL,
                evidence_quote="Atlas used npm before, but we now use pnpm.",
            )
        )
    )
    memory = Memrise(
        store=store,
        jobs=jobs,
        graph_repository=GraphRepositoryStub(available=False),
        graph_projection=build_graph_projection_service(),
        completion_provider=completion,
        embedding_provider=MockEmbeddingProvider(vector=[0.1] * 1024),
        token_counter=ApproximateTokenCounter(),
        feedback_policy=DefaultFeedbackPolicy(),
    )
    return memory, completion


async def test_capture_uses_mock_completion_provider() -> None:
    memory, completion = build_mock_memory()

    capture = await memory.capture(
        namespace_id="it-mock",
        agent_id="coding-agent",
        session_id="session-mock",
        project_id="atlas",
        events=[
            {
                "kind": EpisodeKind.USER_MESSAGE,
                "content": DEMO_EPISODE,
                "metadata": {},
            }
        ],
    )
    assert capture.episode_ids
    assert capture.job_ids
    job = await memory.jobs.get_job(capture.job_ids[0])
    assert job is not None
    await memory.process_job(job)
    await memory.jobs.complete(job.id)
    assert completion.captured
    assert completion.captured[0][0] == DEMO_EPISODE
    assert completion.captured[0][1]["project_id"] == "atlas"


async def test_postgres_concurrent_duplicate_candidate_keeps_single_memory_version() -> None:
    session_factory = make_session_factory(database_url())
    store = PostgresMemoryStore(session_factory, id_generator=UuidGenerator())
    scope = Scope(
        namespace_id=f"it-concurrent-{uuid4().hex}",
        agent_id="coding-agent",
        user_id="user-1",
        project_id="atlas",
    )
    candidate = ExtractedMemoryCandidate(
        type=MemoryType.DECISION,
        subject="Atlas",
        key="package_manager",
        content="Atlas uses pnpm as its package manager.",
        structured_value={"value": "pnpm"},
        confidence=0.9,
        importance=0.8,
        criticality=Criticality.NORMAL,
        evidence_quote="Atlas uses pnpm as its package manager.",
    )

    first_outcome, second_outcome = await asyncio.gather(
        store.apply_candidate(
            scope=scope,
            candidate=candidate,
            source_episode_ids=[],
            embedding=EmbeddingVector(values=[0.1] * 1024, model="mock-embedding", dimensions=1024),
        ),
        store.apply_candidate(
            scope=scope,
            candidate=candidate,
            source_episode_ids=[],
            embedding=EmbeddingVector(values=[0.1] * 1024, model="mock-embedding", dimensions=1024),
        ),
    )
    first = first_outcome.memory
    second = second_outcome.memory

    assert first is not None
    assert second is not None
    assert first.identity.id == second.identity.id
    history = await store.list_memory_history(first.identity.id)
    assert len(history) == 1
    assert history[0].version.status == MemoryStatus.ACTIVE
