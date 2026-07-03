import json
import re
from datetime import datetime
from typing import Any

from memrise.core.enums import GraphEdgeStatus
from memrise.core.graph import GraphEdge, GraphNode, GraphPath
from memrise.core.time import utc_now
from memrise.graph.types import RelationType, coerce_relation

_AGTYPE_SUFFIX = re.compile(r"::(vertex|edge|path|agtype)$")


def _strip_agtype(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return value
    cleaned = _AGTYPE_SUFFIX.sub("", value.strip())
    return json.loads(cleaned)


def parse_vertex(value: Any) -> GraphNode | None:
    payload = _strip_agtype(value)
    if not isinstance(payload, dict):
        return None
    properties = payload.get("properties") or {}
    node_type_raw = properties.get("type")
    if node_type_raw is None:
        return None
    node_type = str(node_type_raw).strip()
    if not node_type:
        return None
    uid = str(properties.get("uid", ""))
    namespace_id = str(properties.get("namespace_id", ""))
    if not uid or not namespace_id:
        return None
    aliases = properties.get("aliases") or []
    return GraphNode(
        uid=uid,
        namespace_id=namespace_id,
        node_type=node_type,
        canonical_name=str(properties.get("canonical_name", "")),
        normalized_name=str(properties.get("normalized_name", "")),
        aliases=tuple(str(alias) for alias in aliases),
    )


def parse_edge(value: Any) -> GraphEdge | None:
    payload = _strip_agtype(value)
    if not isinstance(payload, dict):
        return None
    properties = payload.get("properties") or {}
    uid = str(properties.get("uid", ""))
    namespace_id = str(properties.get("namespace_id", ""))
    source_uid = str(properties.get("source_uid", ""))
    target_uid = str(properties.get("target_uid", ""))
    memory_version_id = str(properties.get("source_memory_version_id", ""))
    if not uid or not namespace_id or not source_uid or not target_uid or not memory_version_id:
        return None
    relation = coerce_relation(str(properties.get("relation", RelationType.RELATED_TO.value)))
    status = GraphEdgeStatus(str(properties.get("status", GraphEdgeStatus.ACTIVE.value)))
    return GraphEdge(
        uid=uid,
        namespace_id=namespace_id,
        source_uid=source_uid,
        target_uid=target_uid,
        relation=relation,
        source_memory_version_id=memory_version_id,
        status=status,
        confidence=float(properties.get("confidence", 0.0)),
        usefulness_score=float(properties.get("usefulness_score", 0.5)),
        valid_from=_parse_datetime(properties.get("valid_from")) or utc_now(),
        valid_until=_parse_datetime(properties.get("valid_until")),
    )


def edge_claim_id(value: Any) -> str | None:
    payload = _strip_agtype(value)
    if not isinstance(payload, dict):
        return None
    claim_id = (payload.get("properties") or {}).get("claim_id")
    if claim_id is None:
        return None
    text = str(claim_id).strip()
    return text or None


def _parse_datetime(value: Any):

    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def build_path(
    *,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    seed_match_score: float,
) -> GraphPath | None:
    if not edges:
        return None
    memory_ids = tuple(
        dict.fromkeys(
            edge.source_memory_version_id for edge in edges if edge.source_memory_version_id
        )
    )
    confidence = min(edge.confidence for edge in edges)
    return GraphPath(
        nodes=tuple(nodes),
        edges=tuple(edges),
        source_memory_version_ids=memory_ids,
        path_length=len(edges),
        path_confidence=confidence,
        seed_match_score=seed_match_score,
    )
