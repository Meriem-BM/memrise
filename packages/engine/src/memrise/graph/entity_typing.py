from typing import Any, Literal

from memrise.core.enums import MemoryType
from memrise.core.models import CanonicalMemory
from memrise.core.text import normalize_lookup
from memrise.graph.ontology import NodeType, coerce_node_type

GraphEndpointRole = Literal["source", "target"]


def resolve_graph_node_type(
    *,
    name: str,
    declared_type: str | None,
    memory: CanonicalMemory | None = None,
    role: GraphEndpointRole,
) -> NodeType:
    if declared_type:
        return coerce_node_type(declared_type)

    if memory is not None:
        applicability_type = _type_from_applicability(
            name=name,
            applicability=memory.version.applicability,
            role=role,
        )
        if applicability_type is not None:
            return applicability_type

        structured_type = _type_from_structured_value(
            name=name,
            memory=memory,
            role=role,
        )
        if structured_type is not None:
            return structured_type

        if normalize_lookup(name) == normalize_lookup(memory.identity.subject):
            return default_node_type_for_memory(memory)

    return NodeType.CONCEPT


def default_node_type_for_memory(memory: CanonicalMemory) -> NodeType:
    match memory.identity.type:
        case MemoryType.GOAL:
            return NodeType.TASK
        case MemoryType.CONSTRAINT:
            return NodeType.COMPONENT
        case _:
            return NodeType.CONCEPT


def _type_from_applicability(
    *,
    name: str,
    applicability: dict[str, Any],
    role: GraphEndpointRole,
) -> NodeType | None:
    entity_types = applicability.get("graph_entity_types")
    if not isinstance(entity_types, dict):
        role_key = f"{role}_entity_type"
        declared = applicability.get(role_key)
        if isinstance(declared, str):
            return coerce_node_type(declared)
        return None

    normalized_name = normalize_lookup(name)
    for raw_name, raw_type in entity_types.items():
        if normalize_lookup(str(raw_name)) == normalized_name and isinstance(raw_type, str):
            return coerce_node_type(raw_type)
    return None


def _type_from_structured_value(
    *,
    name: str,
    memory: CanonicalMemory,
    role: GraphEndpointRole,
) -> NodeType | None:
    structured = memory.version.structured_value
    if role == "source" and normalize_lookup(name) == normalize_lookup(memory.identity.subject):
        declared = structured.get("entity_type") or structured.get("subject_entity_type")
        if isinstance(declared, str):
            return coerce_node_type(declared)

    object_name = structured.get("object")
    object_type = structured.get("object_entity_type")
    if (
        role == "target"
        and isinstance(object_name, str)
        and isinstance(object_type, str)
        and normalize_lookup(name) == normalize_lookup(object_name)
    ):
        return coerce_node_type(object_type)
    return None
