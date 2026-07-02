from tests.mocks.memory_store import make_memory

from memrise.graph.projection_builder import build_graph_projection
from memrise.ports.providers import ExtractedGraphRelation


def test_build_graph_projection_returns_none_when_confidence_is_low() -> None:
    memory = make_memory(confidence=0.2, content="Atlas uses pnpm.")

    projection = build_graph_projection(
        memory=memory,
        relations=[
            ExtractedGraphRelation(source="Atlas", relation="USES", target="pnpm"),
        ],
        min_confidence=0.5,
    )

    assert projection is None


def test_build_graph_projection_builds_nodes_and_edges() -> None:
    memory = make_memory(confidence=0.9, content="Atlas uses pnpm.")

    projection = build_graph_projection(
        memory=memory,
        relations=[
            ExtractedGraphRelation(source="Atlas", relation="USES", target="pnpm"),
        ],
        min_confidence=0.5,
    )

    assert projection is not None
    assert projection.memory_version_id == memory.version.id
    assert len(projection.nodes) == 2
    assert len(projection.edges) == 1
    assert projection.edges[0].relation == "USES"
