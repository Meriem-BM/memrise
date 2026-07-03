from tests.mocks.memory_store import make_memory

from memrise.graph.projection import build_graph_projection
from memrise.ports.providers import ExtractedGraphRelation


def test_build_graph_projection_returns_none_for_low_confidence() -> None:
    memory = make_memory(confidence=0.2)

    projection = build_graph_projection(
        memory=memory,
        relations=[
            ExtractedGraphRelation(
                source="A",
                source_type="Person",
                relation="WORKS_ON",
                target="B",
                target_type="Project",
            )
        ],
        min_confidence=0.5,
    )

    assert projection is None
