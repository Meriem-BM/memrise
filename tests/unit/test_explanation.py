from datetime import UTC, datetime

from memrise.core.enums import GraphEdgeStatus, MemoryStatus
from memrise.core.graph import GraphEdge
from memrise.core.models import MemorySource
from memrise.read.explanation import ExplanationService
from tests.mocks.graph_repository import ExplanationGraphRepository
from tests.mocks.memory_store import ExplanationMemoryStore, make_memory


def _edge(*, version_id: str, edge_id: str = "edge_1") -> GraphEdge:
    now = datetime.now(UTC)
    return GraphEdge(
        uid=edge_id,
        namespace_id="ns",
        source_uid="node_atlas",
        target_uid="node_pnpm",
        relation="USES",
        source_memory_version_id=version_id,
        status=GraphEdgeStatus.ACTIVE,
        confidence=0.9,
        usefulness_score=0.5,
        valid_from=now,
    )


async def test_explanation_includes_history_and_provenance() -> None:
    version_one = make_memory(
        version_id="memv_1",
        content="Atlas used npm.",
        status=MemoryStatus.SUPERSEDED,
    )
    version_two = make_memory(
        memory_id=version_one.identity.id,
        version_id="memv_2",
        content="Atlas uses pnpm.",
        version_number=2,
        status=MemoryStatus.ACTIVE,
    )
    store = ExplanationMemoryStore(
        history_by_memory_id={version_one.identity.id: [version_one, version_two]},
        sources_by_version_id={
            "memv_1": [],
            "memv_2": [],
        },
    )
    store.sources_by_version_id["memv_1"] = [
        MemorySource(
            memory_version_id="memv_1",
            episode_id="episode_1",
            relation="source",
        )
    ]
    service = ExplanationService(store)

    explanation = await service.explain(version_one.identity.id)

    assert explanation.memory_id == version_one.identity.id
    assert explanation.current_version is not None
    assert explanation.current_version.memory_version_id == "memv_2"
    assert len(explanation.versions) == 2
    assert explanation.provenance_episode_ids == ["episode_1"]
    assert explanation.graph_edges == []


async def test_explanation_includes_graph_edges_when_repository_is_available() -> None:
    memory = make_memory(version_id="memv_graph")
    graph = ExplanationGraphRepository(
        available=True,
        edges_by_version={"memv_graph": [_edge(version_id="memv_graph")]},
    )
    store = ExplanationMemoryStore(
        history_by_memory_id={memory.identity.id: [memory]},
    )
    service = ExplanationService(store, graph_repository=graph)

    explanation = await service.explain(memory.identity.id)

    assert len(explanation.graph_edges) == 1
    assert explanation.graph_edges[0]["id"] == "edge_1"
    assert explanation.graph_edges[0]["relation"] == "USES"
