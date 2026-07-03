from dataclasses import replace
from datetime import UTC, datetime

from memrise.core.enums import (
    FeedbackOutcome,
    FeedbackSource,
    GraphClaimStatus,
    MemoryStatus,
)
from memrise.core.graph import GraphClaim
from memrise.learning.policy import DefaultFeedbackPolicy
from memrise.runtime.memory import Memrise
from memrise.runtime.token_counter import ApproximateTokenCounter
from tests.mocks.graph_repository import GraphRepositoryStub
from tests.mocks.graph_services import build_graph_projection_service
from tests.mocks.graph_store import GraphClaimStoreStub
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


def _claim(claim_id: str) -> GraphClaim:
    return GraphClaim(
        id=claim_id,
        namespace_id="ns",
        subject_entity_id="gent-a",
        predicate="USES",
        object_entity_id="gent-b",
        supporting_memory_version_id="memv_test",
        evidence_text="Atlas uses pnpm.",
        confidence=0.9,
        usefulness_score=0.5,
        status=GraphClaimStatus.ACTIVE,
        valid_from=NOW,
        valid_until=None,
        superseded_by_claim_id=None,
        schema_version="core@1.0",
        extractor_version=None,
        extracted_at=NOW,
    )


def _memrise(
    store: MemoryStoreStub,
    graph_repository: GraphRepositoryStub,
    claim_store: GraphClaimStoreStub,
) -> Memrise:
    return Memrise(
        store=store,
        jobs=JobQueueStub(),
        graph_repository=graph_repository,
        graph_projection=build_graph_projection_service(
            graph_repository=graph_repository, claim_store=claim_store
        ),
        graph_claim_store=claim_store,
        completion_provider=MockCompletionProvider(result=no_memory_result()),
        embedding_provider=MockEmbeddingProvider(),
        token_counter=ApproximateTokenCounter(),
        feedback_policy=DefaultFeedbackPolicy(),
    )


async def test_edge_feedback_propagates_to_backing_claim() -> None:
    memory = make_memory(usefulness_score=0.5)
    store = MemoryStoreStub(memories=[memory])
    claim_store = GraphClaimStoreStub()
    claim_store.claims["gclm-1"] = _claim("gclm-1")
    graph_repository = GraphRepositoryStub(claim_id_by_edge={"edge-1": "gclm-1"})
    memrise = _memrise(store, graph_repository, claim_store)

    response = await memrise.feedback(
        "retrieval_1",
        outcome=FeedbackOutcome.HELPFUL,
        source=FeedbackSource.USER,
        memory_version_id=memory.version.id,
        graph_edge_id="edge-1",
    )

    assert response.usefulness_score is not None
    assert graph_repository.usefulness_updates == [("edge-1", response.usefulness_score)]
    assert claim_store.claims["gclm-1"].usefulness_score == response.usefulness_score


async def test_repeated_harmful_feedback_expires_the_version() -> None:
    memory = make_memory(usefulness_score=0.2)
    store = MemoryStoreStub(memories=[memory])
    claim_store = GraphClaimStoreStub()
    graph_repository = GraphRepositoryStub(available=False)
    memrise = _memrise(store, graph_repository, claim_store)

    await memrise.feedback(
        "retrieval_1",
        outcome=FeedbackOutcome.HARMFUL,
        source=FeedbackSource.USER,
        memory_version_id=memory.version.id,
    )

    updated = store.memories[0].version
    assert updated.usefulness_score == 0.0
    assert updated.status == MemoryStatus.EXPIRED


async def test_rebuild_preserves_claim_usefulness() -> None:
    claim = replace(_claim("gclm-1"), usefulness_score=0.9)
    from memrise.graph.projection import build_projection_from_active_claims

    projection = build_projection_from_active_claims(
        memory=make_memory(),
        claims=[claim],
        entity_name_by_id={"gent-a": "Atlas", "gent-b": "pnpm"},
        entity_type_by_id={"gent-a": "Project", "gent-b": "Technology"},
    )

    assert projection is not None
    assert projection.edges[0].usefulness_score == 0.9
