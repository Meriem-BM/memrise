from enum import StrEnum

from memrise.core.text import normalize_lookup

DEFAULT_NODE_TYPE = "Concept"


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
    OWNS = "OWNS"
    AFFECTS = "AFFECTS"
    RELATED_TO = "RELATED_TO"
    CO_OCCURS_WITH = "CO_OCCURS_WITH"
    MENTIONED_WITH = "MENTIONED_WITH"
    POSSIBLY_RELATED = "POSSIBLY_RELATED"


def normalize_entity_name(name: str) -> str:
    return normalize_lookup(name)


def coerce_node_label(value: str | None, *, default: str = DEFAULT_NODE_TYPE) -> str:
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default


def coerce_relation(value: str) -> str:
    normalized = value.strip().upper().replace(" ", "_")
    if not normalized:
        msg = "graph relation must not be empty"
        raise ValueError(msg)
    try:
        return RelationType(normalized).value
    except ValueError:
        msg = f"unsupported graph relation: {value}"
        raise ValueError(msg) from None
