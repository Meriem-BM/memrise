from memrise.core.enums import MemoryType
from memrise.graph.entities import default_node_type_for_memory, resolve_graph_node_type
from memrise.graph.projection import build_graph_projection
from memrise.ports.providers import ExtractedGraphRelation
from tests.mocks.memory_store import make_memory


def test_resolve_graph_node_type_uses_declared_provider_types() -> None:
    node_type = resolve_graph_node_type(
        name="Acme Billing",
        declared_type="Organization",
        memory=None,
        role="source",
    )

    assert node_type == "Organization"


def test_resolve_graph_node_type_uses_applicability_entity_map() -> None:
    memory = make_memory(
        subject="Acme Billing",
        applicability={"graph_entity_types": {"Stripe": "Technology"}},
    )

    node_type = resolve_graph_node_type(
        name="Stripe",
        declared_type=None,
        memory=memory,
        role="target",
    )

    assert node_type == "Technology"


def test_default_node_type_for_memory_maps_goals_to_tasks() -> None:
    memory = make_memory(subject="Ship billing export", type=MemoryType.GOAL)

    assert default_node_type_for_memory(memory) == "Task"


def test_build_graph_projection_uses_typed_relations() -> None:
    memory = make_memory(confidence=0.9, subject="Acme Billing")

    projection = build_graph_projection(
        memory=memory,
        relations=[
            ExtractedGraphRelation(
                source="Acme Billing",
                source_type="Organization",
                relation="USES",
                target="Stripe",
                target_type="Technology",
            )
        ],
        min_confidence=0.5,
    )

    assert projection is not None
    node_types = {node.temporary_id: node.node_type for node in projection.nodes}
    assert node_types["Acme Billing"] == "Organization"
    assert node_types["Stripe"] == "Technology"
