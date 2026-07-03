from datetime import UTC, datetime

import pytest

from memrise.core.enums import EpisodeKind
from memrise.core.models import Episode
from memrise.graph.schema import (
    DomainRoute,
    InMemoryGraphSchemaRegistry,
    prepare_relations,
    route_for_memory,
    validate_relations,
)
from memrise.ports.providers import ExtractedGraphRelation
from tests.mocks.memory_store import make_memory


@pytest.mark.asyncio
async def test_domain_router_selects_software_pack_for_service_content() -> None:
    registry = InMemoryGraphSchemaRegistry()
    memory = make_memory(content="The checkout service depends on PostgreSQL database.")

    routes = await route_for_memory(registry, memory)

    assert routes
    assert any(route.domain == "software_engineering" for route in routes)


@pytest.mark.asyncio
async def test_validation_accepts_core_relation_pattern() -> None:
    registry = InMemoryGraphSchemaRegistry()
    packs = await registry.list_active_packs(namespace_id="ns")
    routes = [
        DomainRoute(domain=pack.domain, confidence=1.0, pack=pack)
        for pack in packs
        if pack.domain == "core"
    ]

    validated = await validate_relations(
        registry,
        namespace_id="ns",
        project_id=None,
        routes=routes,
        relations=[
            ExtractedGraphRelation(
                source="Alice",
                source_type="Person",
                relation="WORKS_ON",
                target="Atlas",
                target_type="Project",
            )
        ],
    )

    assert len(validated) == 1
    assert validated[0].relation == "WORKS_ON"


@pytest.mark.asyncio
async def test_extraction_pipeline_merges_structured_relations() -> None:
    registry = InMemoryGraphSchemaRegistry()
    memory = make_memory(
        confidence=0.9,
        content="ignored",
        structured_value={
            "author_id": "user_1",
            "repository_id": "repo_4",
            "author_entity_type": "Person",
            "repository_entity_type": "Repository",
        },
    )

    routes, validated = await prepare_relations(
        registry,
        memory=memory,
        model_relations=[],
        episode=Episode(
            id="ep1",
            namespace_id="ns",
            agent_id="agent",
            session_id="session",
            kind=EpisodeKind.TOOL_RESULT,
            content="ignored",
            created_at=datetime.now(UTC),
            metadata={"author_id": "user_9", "repository_id": "repo_9"},
        ),
    )

    assert routes
    assert validated
