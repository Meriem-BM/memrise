from memrise.graph.projection import GraphProjectionService, GraphRebuildService
from memrise.graph.schema import InMemoryGraphSchemaRegistry
from tests.mocks.graph_repository import GraphRepositoryStub
from tests.mocks.graph_store import GraphClaimStoreStub


def build_graph_projection_service(
    *,
    graph_repository: GraphRepositoryStub | None = None,
    claim_store: GraphClaimStoreStub | None = None,
    min_confidence: float = 0.5,
) -> GraphProjectionService:
    repository = graph_repository or GraphRepositoryStub(available=False)
    store = claim_store or GraphClaimStoreStub()
    schema_registry = InMemoryGraphSchemaRegistry()
    return GraphProjectionService(
        graph_repository=repository,
        graph_claim_store=store,
        schema_registry=schema_registry,
        min_confidence=min_confidence,
    )


def build_graph_rebuild_service(
    *,
    claim_store: GraphClaimStoreStub | None = None,
    memory_store,
    graph_projection: GraphProjectionService | None = None,
) -> GraphRebuildService:
    store = claim_store or GraphClaimStoreStub()
    projection = graph_projection or build_graph_projection_service(
        claim_store=store,
        graph_repository=GraphRepositoryStub(available=False),
    )
    return GraphRebuildService(
        claim_store=store,
        memory_store=memory_store,
        graph_projection=projection,
    )
