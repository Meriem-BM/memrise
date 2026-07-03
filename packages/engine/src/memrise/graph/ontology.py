from enum import StrEnum

from memrise.core.text import normalize_lookup


class NodeType(StrEnum):
    PERSON = "Person"
    PROJECT = "Project"
    ORGANIZATION = "Organization"
    TECHNOLOGY = "Technology"
    COMPONENT = "Component"
    CONCEPT = "Concept"
    TASK = "Task"


class RelationType(StrEnum):
    WORKS_ON = "WORKS_ON"
    USES = "USES"
    DEPENDS_ON = "DEPENDS_ON"
    PREFERS = "PREFERS"
    BELONGS_TO = "BELONGS_TO"
    REPLACED = "REPLACED"
    CAUSED = "CAUSED"
    BLOCKED_BY = "BLOCKED_BY"
    DEPLOYS_ON = "DEPLOYS_ON"
    RELATED_TO = "RELATED_TO"


def node_type_values() -> tuple[str, ...]:
    return tuple(item.value for item in NodeType)


def coerce_node_type(value: str | None, *, default: NodeType = NodeType.CONCEPT) -> NodeType:
    if value is None:
        return default
    stripped = value.strip()
    if not stripped:
        return default
    try:
        return NodeType(stripped)
    except ValueError:
        normalized = stripped.casefold()
        for candidate in NodeType:
            if candidate.value.casefold() == normalized:
                return candidate
        return default


def ensure_allowed_node_type(value: str) -> NodeType:
    try:
        return NodeType(value.strip())
    except ValueError:
        msg = f"unsupported graph node type: {value}"
        raise ValueError(msg) from None


def ensure_allowed_relation(value: str) -> RelationType:
    normalized = value.strip().upper().replace(" ", "_")
    try:
        return RelationType(normalized)
    except ValueError:
        return RelationType.RELATED_TO


def normalize_entity_name(name: str) -> str:
    return normalize_lookup(name)
