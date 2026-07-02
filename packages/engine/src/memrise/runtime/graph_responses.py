from memrise.core.graph import GraphPath
from memrise.schemas.responses import GraphEdgeSummary, GraphNeighborhoodResponse, GraphNodeSummary


def build_graph_neighborhood_response(
    paths: list[GraphPath],
    *,
    project_id: str | None,
) -> GraphNeighborhoodResponse:
    nodes: list[GraphNodeSummary] = []
    edges: list[GraphEdgeSummary] = []
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()
    for path in paths:
        for node in path.nodes:
            if node.uid in seen_nodes:
                continue
            seen_nodes.add(node.uid)
            nodes.append(
                GraphNodeSummary(
                    id=node.uid,
                    namespace_id=node.namespace_id,
                    node_type=node.node_type,
                    canonical_name=node.canonical_name,
                    normalized_name=node.normalized_name,
                    aliases=list(node.aliases),
                    metadata={},
                    project_id=project_id,
                )
            )
        for edge in path.edges:
            if edge.uid in seen_edges:
                continue
            seen_edges.add(edge.uid)
            edges.append(
                GraphEdgeSummary(
                    id=edge.uid,
                    source_node_id=edge.source_uid,
                    target_node_id=edge.target_uid,
                    relation=edge.relation,
                    source_memory_version_id=edge.source_memory_version_id,
                    status=edge.status,
                    confidence=edge.confidence,
                    usefulness_score=edge.usefulness_score,
                    valid_from=edge.valid_from,
                    valid_until=edge.valid_until,
                )
            )
    return GraphNeighborhoodResponse(nodes=nodes, edges=edges)
