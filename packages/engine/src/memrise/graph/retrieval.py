import re

from memrise.core.graph import GraphPath, GraphSearchRequest, clamp_graph_depth
from memrise.graph.entities import EntityResolver
from memrise.ports.graph_repository import GraphRepository
from memrise.ports.graph_store import GraphClaimStore

_GENERIC_PROMPTS = re.compile(
    r"\b(format|style|tone|write|explain how to|summarize|translate)\b",
    re.IGNORECASE,
)


def should_use_graph_retrieval(query: str) -> bool:
    """Cheap negative filter; entity resolution inside traversal is the real gate."""
    normalized = query.strip().lower()
    if not normalized:
        return False
    return not _GENERIC_PROMPTS.search(normalized)


class GraphTraversalService:
    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        claim_store: GraphClaimStore,
        min_edge_confidence: float = 0.4,
    ) -> None:
        self._graph_repository = graph_repository
        self._claim_store = claim_store
        self._min_edge_confidence = min_edge_confidence

    async def traverse_for_query(
        self,
        *,
        namespace_id: str,
        query: str,
        depth: int,
        project_id: str | None = None,
        max_paths: int = 20,
    ) -> list[GraphPath]:
        if not await self._graph_repository.is_available():
            return []

        resolver = EntityResolver(claim_store=self._claim_store)
        seeds = await resolver.resolve_query_terms(
            namespace_id=namespace_id,
            query=query,
            project_id=project_id,
        )

        if not seeds:
            # No known entities in the query: graph traversal has nothing
            # grounded to walk from, so stay out of the fused ranking.
            return []

        paths: list[GraphPath] = []
        seen_path_keys: set[str] = set()
        bounded_depth = clamp_graph_depth(depth)
        for entity in seeds:
            entity_paths = await self._graph_repository.search(
                GraphSearchRequest(
                    namespace_id=namespace_id,
                    query=entity.normalized_name,
                    depth=bounded_depth,
                    max_paths=max_paths,
                    exact_match=True,
                )
            )
            for path in entity_paths:
                if path.path_confidence < self._min_edge_confidence:
                    continue
                key = _path_key(path)
                if key in seen_path_keys:
                    continue
                seen_path_keys.add(key)
                paths.append(path)
        return paths[:max_paths]


def _path_key(path: GraphPath) -> str:
    edge_ids = ",".join(edge.uid for edge in path.edges)
    return f"{path.path_length}:{edge_ids}"
