import os

import pytest
from tests.mocks.graph_repository import GraphRepositoryStub
from tests.mocks.providers import (
    MockCompletionProvider,
    MockEmbeddingProvider,
    single_candidate_result,
)

from memrise.consolidation.graph_projection import GraphProjectionService
from memrise.core.enums import Criticality, EpisodeKind, MemoryType
from memrise.integrations.postgres.repositories import PostgresMemoryStore
from memrise.integrations.postgres.session import make_session_factory
from memrise.learning.policy import DefaultFeedbackPolicy
from memrise.ports.providers import ExtractedMemoryCandidate
from memrise.runtime.ids import UuidGenerator
from memrise.runtime.memory import Memrise
from memrise.runtime.token_counter import ApproximateTokenCounter

pytestmark = pytest.mark.asyncio

DEMO_EPISODE = (
    "Atlas used npm before, but we now use pnpm. Never edit its generated lockfile manually."
)


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL is required for PostgreSQL integration tests")
    return url


def build_mock_memory() -> tuple[Memrise, MockCompletionProvider]:
    url = database_url()
    session_factory = make_session_factory(url)
    id_generator = UuidGenerator()
    store = PostgresMemoryStore(session_factory, id_generator=id_generator)
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
            )
        )
    )
    memory = Memrise(
        store=store,
        jobs=store,
        graph_repository=GraphRepositoryStub(available=False),
        graph_projection=GraphProjectionService(
            graph_repository=GraphRepositoryStub(available=False)
        ),
        completion_provider=completion,
        embedding_provider=MockEmbeddingProvider(),
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
    assert await memory.process_job_once("mock-worker")
    assert completion.captured
    assert completion.captured[0][0] == DEMO_EPISODE
    assert completion.captured[0][1]["project_id"] == "atlas"
