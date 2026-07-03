import re
from dataclasses import dataclass
from typing import Any, Literal

from memrise.core.enums import MemoryType
from memrise.core.graph import GraphEntity
from memrise.core.models import CanonicalMemory
from memrise.core.text import normalize_lookup
from memrise.graph.identity import stable_entity_id
from memrise.graph.types import DEFAULT_NODE_TYPE, coerce_node_label, normalize_entity_name
from memrise.ports.graph_store import GraphClaimStore

GraphEndpointRole = Literal["source", "target"]
EntityResolutionStatus = Literal["resolved", "new_entity", "ambiguous", "rejected"]

_QUERY_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "at",
        "be",
        "by",
        "did",
        "do",
        "does",
        "for",
        "how",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
    }
)


@dataclass(frozen=True, slots=True)
class EntityMention:
    name: str
    type_hint: str | None = None
    stable_source_id: str | None = None


@dataclass(frozen=True, slots=True)
class EntityResolutionResult:
    status: EntityResolutionStatus
    entity_id: str | None = None
    canonical_name: str | None = None
    core_type: str | None = None
    domain_type: str | None = None
    candidates: tuple[str, ...] = ()


def resolve_graph_node_type(
    *,
    name: str,
    declared_type: str | None,
    memory: CanonicalMemory | None = None,
    role: GraphEndpointRole,
) -> str:
    if declared_type:
        return coerce_node_label(declared_type)

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

    return DEFAULT_NODE_TYPE


def default_node_type_for_memory(memory: CanonicalMemory) -> str:
    match memory.identity.type:
        case MemoryType.GOAL:
            return "Task"
        case MemoryType.CONSTRAINT:
            return "Component"
        case _:
            return DEFAULT_NODE_TYPE


class EntityResolver:
    def __init__(self, *, claim_store: GraphClaimStore) -> None:
        self._claim_store = claim_store

    async def resolve(
        self,
        *,
        mention: EntityMention,
        namespace_id: str,
        core_type: str,
        domain_type: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> EntityResolutionResult:
        if mention.stable_source_id:
            entity = await self._claim_store.get_entity_by_stable_source_id(
                namespace_id=namespace_id,
                stable_source_id=mention.stable_source_id,
            )
            if entity is not None:
                return _resolved(entity)

        normalized = normalize_entity_name(mention.name)
        exact = await self._claim_store.get_entity_by_identity(
            namespace_id=namespace_id,
            core_type=core_type,
            normalized_name=normalized,
        )
        if exact is not None:
            return _resolved(exact)

        alias_matches = await self._claim_store.find_entities_by_term(
            namespace_id=namespace_id,
            term=mention.name,
            core_type=core_type,
            user_id=user_id,
            project_id=project_id,
            limit=5,
        )
        if len(alias_matches) == 1:
            return _resolved(alias_matches[0])
        if len(alias_matches) > 1:
            return EntityResolutionResult(
                status="ambiguous",
                candidates=tuple(item.id for item in alias_matches),
            )

        return EntityResolutionResult(
            status="new_entity",
            entity_id=stable_entity_id(
                namespace_id=namespace_id,
                core_type=core_type,
                name=mention.name,
            ),
            canonical_name=mention.name.strip(),
            core_type=core_type,
            domain_type=domain_type,
        )

    async def resolve_query_terms(
        self,
        *,
        namespace_id: str,
        query: str,
        project_id: str | None = None,
    ) -> list[GraphEntity]:
        resolved: list[GraphEntity] = []
        seen: set[str] = set()
        for term in query_search_terms(query):
            matches = await self._claim_store.find_entities_by_term(
                namespace_id=namespace_id,
                term=term,
                core_type=None,
                project_id=project_id,
                limit=3,
            )
            for entity in matches:
                if entity.id in seen:
                    continue
                seen.add(entity.id)
                resolved.append(entity)
        return resolved


def query_search_terms(query: str) -> list[str]:
    stripped = query.strip().rstrip("?").strip()
    if not stripped:
        return []

    tokens = _query_tokens(stripped)
    content_tokens = [token for token in tokens if token.casefold() not in _QUERY_STOPWORDS]

    ordered: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        text = " ".join(term.split())
        if len(text) < 3:
            return
        key = normalize_entity_name(text)
        if key in seen:
            return
        seen.add(key)
        ordered.append(text)

    add(stripped)
    for size in (3, 2):
        for index in range(len(content_tokens) - size + 1):
            add(" ".join(content_tokens[index : index + size]))
    for token in content_tokens:
        add(token)
    return ordered


def _query_tokens(text: str) -> list[str]:
    return [
        part.strip(".,:;!?()[]{}\"'")
        for part in re.split(r"\s+", text)
        if part.strip(".,:;!?()[]{}\"'")
    ]


def _resolved(entity: GraphEntity) -> EntityResolutionResult:
    return EntityResolutionResult(
        status="resolved",
        entity_id=entity.id,
        canonical_name=entity.canonical_name,
        core_type=entity.core_type,
        domain_type=entity.domain_type,
    )


def _type_from_applicability(
    *,
    name: str,
    applicability: dict[str, Any],
    role: GraphEndpointRole,
) -> str | None:
    entity_types = applicability.get("graph_entity_types")
    if not isinstance(entity_types, dict):
        role_key = f"{role}_entity_type"
        declared = applicability.get(role_key)
        if isinstance(declared, str):
            return coerce_node_label(declared)
        return None

    normalized_name = normalize_lookup(name)
    for raw_name, raw_type in entity_types.items():
        if normalize_lookup(str(raw_name)) == normalized_name and isinstance(raw_type, str):
            return coerce_node_label(raw_type)
    return None


def _type_from_structured_value(
    *,
    name: str,
    memory: CanonicalMemory,
    role: GraphEndpointRole,
) -> str | None:
    structured = memory.version.structured_value
    if role == "source" and normalize_lookup(name) == normalize_lookup(memory.identity.subject):
        declared = structured.get("entity_type") or structured.get("subject_entity_type")
        if isinstance(declared, str):
            return coerce_node_label(declared)

    object_name = structured.get("object")
    object_type = structured.get("object_entity_type")
    if (
        role == "target"
        and isinstance(object_name, str)
        and isinstance(object_type, str)
        and normalize_lookup(name) == normalize_lookup(object_name)
    ):
        return coerce_node_label(object_type)
    return None
