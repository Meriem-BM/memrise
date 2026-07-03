from datetime import UTC, datetime

from memrise.core.enums import GraphClaimStatus
from memrise.graph.retrieval import GraphTraversalService
from memrise.ports.providers import ExtractedGraphRelation
from tests.mocks.graph_repository import GraphRepositoryStub
from tests.mocks.graph_services import build_graph_projection_service
from tests.mocks.graph_store import GraphClaimStoreStub
from tests.mocks.memory_store import make_memory

NOW = datetime(2026, 7, 3, tzinfo=UTC)


async def test_traversal_without_resolved_seeds_returns_nothing() -> None:
    repository = GraphRepositoryStub()
    service = GraphTraversalService(
        graph_repository=repository,
        claim_store=GraphClaimStoreStub(),
    )

    paths = await service.traverse_for_query(
        namespace_id="ns",
        query="completely unknown thing",
        depth=1,
    )

    assert paths == []
    assert repository.search_requests == []


async def test_traversal_uses_exact_match_for_resolved_seeds() -> None:
    repository = GraphRepositoryStub()
    claim_store = GraphClaimStoreStub()
    await claim_store.upsert_entity(
        entity_id="gent-atlas",
        namespace_id="ns",
        core_type="Project",
        canonical_name="Atlas",
        normalized_name="atlas",
        aliases=("Atlas",),
    )
    service = GraphTraversalService(graph_repository=repository, claim_store=claim_store)

    await service.traverse_for_query(namespace_id="ns", query="what does Atlas use", depth=1)

    assert repository.search_requests
    assert all(request.exact_match for request in repository.search_requests)
    assert repository.search_requests[0].query == "atlas"


async def test_functional_predicate_supersedes_rival_object() -> None:
    claim_store = GraphClaimStoreStub()
    repository = GraphRepositoryStub()
    service = build_graph_projection_service(graph_repository=repository, claim_store=claim_store)

    def relation(target: str) -> ExtractedGraphRelation:
        return ExtractedGraphRelation(
            source="checkout-service",
            source_type="Component",
            relation="DEPLOYS_ON",
            target=target,
            target_type="System",
        )

    first_memory = make_memory(
        memory_id="mem_deploy",
        version_id="memv_1",
        subject="checkout-service",
        key="deploy_target",
        content="checkout-service deploys on cluster-a.",
    )
    await service.project_memory(memory=first_memory, relations=[relation("cluster-a")])

    second_memory = make_memory(
        memory_id="mem_deploy",
        version_id="memv_2",
        subject="checkout-service",
        key="deploy_target",
        content="checkout-service deploys on cluster-b.",
        version_number=2,
    )
    await service.project_memory(memory=second_memory, relations=[relation("cluster-b")])

    claims = list(claim_store.claims.values())
    active = [claim for claim in claims if claim.status == GraphClaimStatus.ACTIVE]
    superseded = [claim for claim in claims if claim.status == GraphClaimStatus.SUPERSEDED]
    assert len(active) == 1
    assert len(superseded) == 1
    assert superseded[0].superseded_by_claim_id == active[0].id
