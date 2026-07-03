import re

from memrise.core.graph import GraphPath, GraphSearchRequest, clamp_graph_depth
from memrise.graph.entities import EntityResolver
from memrise.ports.graph_repository import GraphRepository
from memrise.ports.graph_store import GraphClaimStore

_RELATION_HINTS = re.compile(
    r"\b(use[sd]?|depend(?:s|ed|ency)?|replace[sd]?|work(?:s|ed|ing)? on|belong(?:s|ed)? to|"
    r"own(?:s|ed|er)?|cause[sd]?|block(?:ed|s)? by|deploy(?:s|ed)? on|connect(?:s|ed)? to|"
    r"related to|who|what|which)\b",
    re.IGNORECASE,
)

_GENERIC_PROMPTS = re.compile(
    r"\b(format|style|tone|write|explain how to|summarize|translate)\b",
    re.IGNORECASE,
)


def should_use_graph_retrieval(query: str) -> bool:
    normalized = query.strip().lower()
    if not normalized:
        return False
    if _GENERIC_PROMPTS.search(normalized):
        return False
    if _RELATION_HINTS.search(normalized):
        return True
    if normalized.endswith("?"):
        return True
    tokens = [token for token in re.split(r"[^\w]+", normalized) if token]
    return len(tokens) >= 2 and any(token[0].isupper() for token in query.split())


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

        paths: list[GraphPath] = []
        seen_path_keys: set[str] = set()
        bounded_depth = clamp_graph_depth(depth)

        if seeds:
            for entity in seeds:
                entity_paths = await self._graph_repository.search(
                    GraphSearchRequest(
                        namespace_id=namespace_id,
                        query=entity.normalized_name,
                        depth=bounded_depth,
                        max_paths=max_paths,
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
        else:
            paths = await self._graph_repository.search(
                GraphSearchRequest(
                    namespace_id=namespace_id,
                    query=query,
                    depth=bounded_depth,
                    max_paths=max_paths,
                )
            )

        claim_backed = await self._claim_store.list_active_claims(namespace_id=namespace_id)
        if claim_backed and not paths:
            for claim in claim_backed[:max_paths]:
                subject = await self._claim_store.get_entity_by_id(claim.subject_entity_id)
                if subject is None:
                    continue
                entity_paths = await self._graph_repository.search(
                    GraphSearchRequest(
                        namespace_id=namespace_id,
                        query=subject.normalized_name,
                        depth=1,
                        max_paths=3,
                    )
                )
                paths.extend(entity_paths)

        return paths[:max_paths]


def _path_key(path: GraphPath) -> str:
    edge_ids = ",".join(edge.uid for edge in path.edges)
    return f"{path.path_length}:{edge_ids}"
