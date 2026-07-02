from memrise.core.graph import GraphEdgeCandidate, GraphNodeCandidate, GraphProjection
from memrise.core.models import CanonicalMemory
from memrise.graph.ontology import NodeType, ensure_allowed_relation, normalize_entity_name
from memrise.ports.providers import ExtractedGraphRelation


def _infer_node_type(name: str) -> NodeType:
    lowered = name.lower()
    if lowered in {"atlas", "memrise"} or lowered.endswith(" project"):
        return NodeType.PROJECT
    if lowered in {"pnpm", "npm", "postgresql", "postgres", "redis", "qwen"}:
        return NodeType.TECHNOLOGY
    return NodeType.CONCEPT


def build_graph_projection(
    *,
    memory: CanonicalMemory,
    relations: list[ExtractedGraphRelation],
    min_confidence: float,
) -> GraphProjection | None:
    if memory.version.confidence < min_confidence:
        return None
    if not relations:
        return None

    node_candidates: dict[str, GraphNodeCandidate] = {}
    edge_candidates: list[GraphEdgeCandidate] = []

    for relation in relations:
        relation_type = ensure_allowed_relation(relation.relation)
        for temporary_id, name in (
            (relation.source, relation.source),
            (relation.target, relation.target),
        ):
            if temporary_id not in node_candidates:
                node_candidates[temporary_id] = GraphNodeCandidate(
                    temporary_id=temporary_id,
                    node_type=_infer_node_type(name).value,
                    name=name.strip(),
                )
        edge_candidates.append(
            GraphEdgeCandidate(
                source=relation.source,
                relation=relation_type.value,
                target=relation.target,
            )
        )

    return GraphProjection(
        memory_version_id=memory.version.id,
        namespace_id=memory.identity.namespace_id,
        confidence=memory.version.confidence,
        valid_from=memory.version.valid_from,
        supersedes_version_id=memory.version.supersedes_version_id,
        nodes=tuple(node_candidates.values()),
        edges=tuple(edge_candidates),
    )


def node_identity_key(*, namespace_id: str, node_type: NodeType | str, name: str) -> str:
    label = node_type.value if isinstance(node_type, NodeType) else node_type
    return f"{namespace_id}:{label}:{normalize_entity_name(name)}"
