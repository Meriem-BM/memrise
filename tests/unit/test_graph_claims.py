from datetime import UTC, datetime

import pytest
from tests.mocks.graph_repository import GraphRepositoryStub
from tests.mocks.graph_services import build_graph_projection_service
from tests.mocks.graph_store import GraphClaimStoreStub
from tests.mocks.memory_store import make_memory

from memrise.core.enums import GraphClaimStatus
from memrise.core.graph import GraphClaim, GraphClaimPersistenceResult, GraphEntity
from memrise.graph.entities import EntityResolver
from memrise.graph.identity import stable_claim_id, stable_entity_id
from memrise.graph.projection import (
    build_graph_projection,
    build_graph_projection_from_claims,
    persist_graph_claims,
)
from memrise.graph.schema import ValidatedGraphRelation
from memrise.ports.providers import ExtractedGraphRelation


@pytest.mark.asyncio
async def test_persist_graph_claims_writes_entities_and_claims() -> None:
    memory = make_memory(confidence=0.9, content="Atlas uses pnpm.")
    validated = [
        ValidatedGraphRelation(
            source="Atlas",
            source_type="Project",
            relation="USES",
            target="pnpm",
            target_type="Technology",
        )
    ]
    projection = build_graph_projection(
        memory=memory,
        relations=[
            ExtractedGraphRelation(
                source="Atlas",
                source_type="Project",
                relation="USES",
                target="pnpm",
                target_type="Technology",
            )
        ],
        min_confidence=0.5,
    )
    assert projection is not None

    store = GraphClaimStoreStub()
    persisted = await persist_graph_claims(
        store=store,
        entity_resolver=EntityResolver(claim_store=store),
        memory=memory,
        projection=projection,
        validated_relations=validated,
    )

    assert len(persisted.entities) == 2
    assert len(persisted.claims) == 1
    assert persisted.claims[0].predicate == "USES"
    assert persisted.claims[0].supporting_memory_version_id == memory.version.id
    assert (
        stable_entity_id(
            namespace_id=memory.identity.namespace_id,
            core_type="Project",
            name="Atlas",
        )
        in store.entities
    )


@pytest.mark.asyncio
async def test_graph_projection_service_persists_claims_before_age_projection() -> None:
    memory = make_memory(confidence=0.9, content="Atlas uses pnpm.")
    relations = [
        ExtractedGraphRelation(
            source="Atlas",
            source_type="Project",
            relation="USES",
            target="pnpm",
            target_type="Technology",
        )
    ]
    graph_repository = GraphRepositoryStub(available=True)
    claim_store = GraphClaimStoreStub()
    service = build_graph_projection_service(
        graph_repository=graph_repository,
        claim_store=claim_store,
        min_confidence=0.5,
    )

    result = await service.project_memory(memory=memory, relations=relations)

    assert result is not None
    assert len(claim_store.claims) == 1
    assert len(graph_repository.projected) == 1
    projected = graph_repository.projected[0]
    assert projected.edges[0].claim_id == next(iter(claim_store.claims))


def test_build_graph_projection_from_claims_attaches_claim_ids() -> None:
    memory = make_memory(confidence=0.9, content="Atlas uses pnpm.")
    relations = [
        ExtractedGraphRelation(
            source="Atlas",
            source_type="Project",
            relation="USES",
            target="pnpm",
            target_type="Technology",
        )
    ]
    projection = build_graph_projection(memory=memory, relations=relations, min_confidence=0.5)
    assert projection is not None

    subject_id = stable_entity_id(
        namespace_id=memory.identity.namespace_id,
        core_type=projection.nodes[0].node_type,
        name=projection.nodes[0].name,
    )
    object_id = stable_entity_id(
        namespace_id=memory.identity.namespace_id,
        core_type=projection.nodes[1].node_type,
        name=projection.nodes[1].name,
    )
    claim_id = stable_claim_id(
        subject_entity_id=subject_id,
        predicate="USES",
        object_entity_id=object_id,
        memory_version_id=memory.version.id,
    )
    now = datetime.now(UTC)
    persisted = GraphClaimPersistenceResult(
        memory_version_id=memory.version.id,
        namespace_id=memory.identity.namespace_id,
        entities=(
            GraphEntity(
                id=subject_id,
                namespace_id=memory.identity.namespace_id,
                core_type=projection.nodes[0].node_type,
                domain_type=None,
                canonical_name=projection.nodes[0].name,
                normalized_name=projection.nodes[0].name.lower(),
                created_at=now,
            ),
            GraphEntity(
                id=object_id,
                namespace_id=memory.identity.namespace_id,
                core_type=projection.nodes[1].node_type,
                domain_type=None,
                canonical_name=projection.nodes[1].name,
                normalized_name=projection.nodes[1].name.lower(),
                created_at=now,
            ),
        ),
        claims=(
            GraphClaim(
                id=claim_id,
                namespace_id=memory.identity.namespace_id,
                subject_entity_id=subject_id,
                predicate="USES",
                object_entity_id=object_id,
                supporting_memory_version_id=memory.version.id,
                evidence_text=memory.version.content,
                confidence=0.9,
                status=GraphClaimStatus.ACTIVE,
                valid_from=memory.version.valid_from,
                valid_until=None,
                superseded_by_claim_id=None,
                schema_version="core@1.0",
                extractor_version=None,
                extracted_at=now,
            ),
        ),
        superseded_claim_count=0,
    )

    rebuilt = build_graph_projection_from_claims(
        memory=memory,
        persisted=persisted,
        projection=projection,
    )
    assert rebuilt.edges[0].claim_id == claim_id
