from typing import Any

from memrise.core.graph import GraphEdge
from memrise.core.models import CanonicalMemory
from memrise.ports.graph_repository import GraphRepository
from memrise.ports.repositories import MemoryStore
from memrise.schemas.mappers import memory_to_summary
from memrise.schemas.responses import MemoryExplanation


def edge_to_dict(edge: GraphEdge) -> dict[str, Any]:
    return {
        "id": edge.uid,
        "source_node_id": edge.source_uid,
        "target_node_id": edge.target_uid,
        "relation": edge.relation,
        "source_memory_version_id": edge.source_memory_version_id,
        "status": edge.status.value,
        "confidence": edge.confidence,
        "usefulness_score": edge.usefulness_score,
        "valid_from": edge.valid_from.isoformat(),
        "valid_until": edge.valid_until.isoformat() if edge.valid_until else None,
    }


class ExplanationService:
    def __init__(
        self,
        store: MemoryStore,
        *,
        graph_repository: GraphRepository | None = None,
    ) -> None:
        self._store = store
        self._graph_repository = graph_repository

    async def explain(self, memory_id: str) -> MemoryExplanation:
        history = await self._store.list_memory_history(memory_id)
        current = next((memory for memory in history if memory.version.is_lifecycle_active), None)
        provenance: list[str] = []
        for memory in history:
            sources = await self._store.list_memory_sources(memory.version.id)
            provenance.extend(source.episode_id for source in sources)
        graph_edges = await self._graph_edges_for_history(history)
        return MemoryExplanation(
            memory_id=memory_id,
            current_version=memory_to_summary(current) if current else None,
            versions=[memory_to_summary(memory) for memory in history],
            provenance_episode_ids=sorted(set(provenance)),
            graph_edges=graph_edges,
            retrieval_feedback=[],
        )

    async def _graph_edges_for_history(
        self, history: list[CanonicalMemory]
    ) -> list[dict[str, Any]]:
        if self._graph_repository is None or not await self._graph_repository.is_available():
            return []
        seen_edge_ids: set[str] = set()
        graph_edges: list[dict[str, Any]] = []
        for memory in history:
            edges = await self._graph_repository.list_edges_for_memory_version(
                namespace_id=memory.identity.namespace_id,
                memory_version_id=memory.version.id,
            )
            for edge in edges:
                if edge.uid in seen_edge_ids:
                    continue
                seen_edge_ids.add(edge.uid)
                graph_edges.append(edge_to_dict(edge))
        return graph_edges
