import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from memrise.core.models import CanonicalMemory, Episode
from memrise.ports.providers import ExtractedGraphRelation

if TYPE_CHECKING:
    from memrise.ports.schema_registry import GraphSchemaRegistry

_SOFTWARE_KEYWORDS = re.compile(
    r"\b(service|repository|repo|database|incident|deploy|api|microservice|kubernetes|docker|"
    r"pull request|github|ci/?cd|backend|frontend|server|postgres|mysql|redis)\b",
    re.IGNORECASE,
)

_KNOWN_RELATIONS = frozenset(
    {
        "WORKS_ON",
        "USES",
        "DEPENDS_ON",
        "PREFERS",
        "BELONGS_TO",
        "REPLACED",
        "CAUSED",
        "BLOCKED_BY",
        "DEPLOYS_ON",
        "RELATED_TO",
        "OWNS",
        "AFFECTS",
        "CO_OCCURS_WITH",
        "MENTIONED_WITH",
        "POSSIBLY_RELATED",
    }
)


@dataclass(frozen=True, slots=True)
class RelationshipPattern:
    source: str
    type: str
    target: str


@dataclass(frozen=True, slots=True)
class GraphSchemaPack:
    id: str
    domain: str
    version: str
    status: str
    namespace_id: str | None
    project_id: str | None
    node_types: tuple[str, ...]
    relationship_patterns: tuple[RelationshipPattern, ...]
    type_aliases: dict[str, str]
    relation_aliases: dict[str, str]
    weak_relations: frozenset[str]
    # Single-valued predicates: at most one active object per (subject, predicate).
    functional_relations: frozenset[str]

    @property
    def version_label(self) -> str:
        return f"{self.domain}@{self.version}"

    def allows_node_type(self, node_type: str) -> bool:
        return node_type in self.node_types

    def allows_weak_relation(self, relation: str) -> bool:
        return relation in self.weak_relations

    def allows_pattern(self, *, source: str, relation: str, target: str) -> bool:
        return any(
            pattern.source == source and pattern.type == relation and pattern.target == target
            for pattern in self.relationship_patterns
        )


@dataclass(frozen=True, slots=True)
class DomainRoute:
    domain: str
    confidence: float
    pack: GraphSchemaPack


@dataclass(frozen=True, slots=True)
class ValidatedGraphRelation:
    source: str
    source_type: str
    relation: str
    target: str
    target_type: str
    is_weak: bool = False
    domain_type: str | None = None


def pack_from_definition(
    *,
    pack_id: str,
    namespace_id: str | None,
    project_id: str | None,
    status: str,
    definition: dict[str, Any],
) -> GraphSchemaPack:
    patterns = tuple(
        RelationshipPattern(
            source=str(item["source"]),
            type=str(item["type"]),
            target=str(item["target"]),
        )
        for item in definition.get("relationship_patterns", [])
    )
    return GraphSchemaPack(
        id=pack_id,
        domain=str(definition.get("domain", "core")),
        version=str(definition.get("version", "1.0")),
        status=status,
        namespace_id=namespace_id,
        project_id=project_id,
        node_types=tuple(str(item) for item in definition.get("node_types", ())),
        relationship_patterns=patterns,
        type_aliases={
            str(key): str(value) for key, value in definition.get("type_aliases", {}).items()
        },
        relation_aliases={
            str(key): str(value) for key, value in definition.get("relation_aliases", {}).items()
        },
        weak_relations=frozenset(
            str(item) for item in definition.get("weak_relations", ("POSSIBLY_RELATED",))
        ),
        functional_relations=frozenset(
            str(item) for item in definition.get("functional_relations", ())
        ),
    )


CORE_PACK_DEFINITION: dict[str, Any] = {
    "domain": "core",
    "version": "1.0",
    "node_types": [
        "Person",
        "Organization",
        "Location",
        "Event",
        "Document",
        "Project",
        "Product",
        "System",
        "Concept",
        "Process",
        "Asset",
        "Decision",
        "Preference",
        "Technology",
        "Component",
        "Task",
        "UnknownEntity",
    ],
    "relationship_patterns": [
        {"source": "Person", "type": "WORKS_ON", "target": "Project"},
        {"source": "Person", "type": "WORKS_ON", "target": "Task"},
        {"source": "Person", "type": "WORKS_ON", "target": "Component"},
        {"source": "Person", "type": "PREFERS", "target": "Technology"},
        {"source": "Person", "type": "PREFERS", "target": "Concept"},
        {"source": "Project", "type": "USES", "target": "Technology"},
        {"source": "Project", "type": "USES", "target": "Component"},
        {"source": "Component", "type": "DEPENDS_ON", "target": "Component"},
        {"source": "Component", "type": "DEPENDS_ON", "target": "Technology"},
        {"source": "Component", "type": "DEPLOYS_ON", "target": "System"},
        {"source": "Task", "type": "BLOCKED_BY", "target": "Task"},
        {"source": "Decision", "type": "REPLACED", "target": "Technology"},
        {"source": "Event", "type": "CAUSED", "target": "Event"},
        {"source": "Organization", "type": "BELONGS_TO", "target": "Project"},
    ],
    "type_aliases": {
        "Business": "Organization",
        "Company": "Organization",
        "Corporation": "Organization",
        "Vendor": "Organization",
        "Service": "Component",
        "Database": "Technology",
        "Repository": "Component",
    },
    "relation_aliases": {},
    "weak_relations": ["CO_OCCURS_WITH", "MENTIONED_WITH", "POSSIBLY_RELATED"],
    "functional_relations": ["BELONGS_TO", "DEPLOYS_ON"],
}

SOFTWARE_PACK_DEFINITION: dict[str, Any] = {
    "domain": "software_engineering",
    "version": "1.0",
    "node_types": [
        "Service",
        "Repository",
        "Database",
        "Incident",
        "Team",
        "Engineer",
        "Component",
        "Technology",
        "Project",
    ],
    "relationship_patterns": [
        {"source": "Team", "type": "OWNS", "target": "Service"},
        {"source": "Engineer", "type": "WORKS_ON", "target": "Service"},
        {"source": "Service", "type": "DEPENDS_ON", "target": "Database"},
        {"source": "Service", "type": "DEPENDS_ON", "target": "Service"},
        {"source": "Incident", "type": "AFFECTS", "target": "Service"},
        {"source": "Repository", "type": "BELONGS_TO", "target": "Project"},
    ],
    "type_aliases": {
        "Microservice": "Service",
        "API": "Service",
        "DB": "Database",
        "Repo": "Repository",
    },
    "relation_aliases": {"AFFECTED": "AFFECTS"},
    "weak_relations": ["CO_OCCURS_WITH", "MENTIONED_WITH", "POSSIBLY_RELATED"],
    "functional_relations": ["BELONGS_TO", "DEPLOYS_ON"],
}


class InMemoryGraphSchemaRegistry:
    def __init__(self) -> None:
        self._packs = [
            pack_from_definition(
                pack_id="schema-core-1.0",
                namespace_id=None,
                project_id=None,
                status="active",
                definition=CORE_PACK_DEFINITION,
            ),
            pack_from_definition(
                pack_id="schema-software-1.0",
                namespace_id=None,
                project_id=None,
                status="active",
                definition=SOFTWARE_PACK_DEFINITION,
            ),
        ]
        self._candidates: list[dict[str, object]] = []

    async def ensure_seeded(self) -> None:
        return None

    async def list_active_packs(
        self,
        *,
        namespace_id: str,
        project_id: str | None = None,
    ) -> list[GraphSchemaPack]:
        del namespace_id, project_id
        return [pack for pack in self._packs if pack.status == "active"]

    async def get_pack(self, pack_id: str) -> GraphSchemaPack | None:
        for pack in self._packs:
            if pack.id == pack_id:
                return pack
        return None

    async def record_schema_candidate(
        self,
        *,
        namespace_id: str,
        domain: str,
        candidate_type: str,
        candidate_kind: str,
        fallback_type: str,
        example: dict[str, object],
    ) -> None:
        self._candidates.append(
            {
                "namespace_id": namespace_id,
                "domain": domain,
                "candidate_type": candidate_type,
                "candidate_kind": candidate_kind,
                "fallback_type": fallback_type,
                "example": example,
            }
        )


def default_schema_registry() -> GraphSchemaRegistry:
    return InMemoryGraphSchemaRegistry()


async def route_schema_packs(
    registry: GraphSchemaRegistry,
    *,
    namespace_id: str,
    project_id: str | None,
    text: str,
) -> list[DomainRoute]:
    packs = await registry.list_active_packs(namespace_id=namespace_id, project_id=project_id)
    routes: list[DomainRoute] = []
    for pack in packs:
        confidence = 0.55 if pack.domain == "core" else 0.35
        if pack.domain == "software_engineering" and _SOFTWARE_KEYWORDS.search(text):
            confidence = 0.9
        if project_id is not None and pack.domain != "core":
            confidence += 0.05
        routes.append(DomainRoute(domain=pack.domain, confidence=confidence, pack=pack))
    routes.sort(key=lambda item: item.confidence, reverse=True)
    return [route for route in routes if route.confidence >= 0.5]


async def route_for_memory(
    registry: GraphSchemaRegistry,
    memory: CanonicalMemory,
) -> list[DomainRoute]:
    return await route_schema_packs(
        registry,
        namespace_id=memory.identity.namespace_id,
        project_id=memory.identity.project_id,
        text=f"{memory.identity.subject} {memory.identity.key} {memory.version.content}",
    )


def extract_structured_relations(
    *,
    memory: CanonicalMemory | None = None,
    episode: Episode | None = None,
) -> list[ExtractedGraphRelation]:
    relations: list[ExtractedGraphRelation] = []
    structured = memory.version.structured_value if memory is not None else {}
    metadata = episode.metadata if episode is not None else {}

    if isinstance(structured, dict):
        author = structured.get("author_id")
        repository = structured.get("repository_id")
        if author and repository:
            relations.append(
                ExtractedGraphRelation(
                    source=str(author),
                    source_type=_as_str(structured.get("author_entity_type")) or "Person",
                    relation="WORKS_ON",
                    target=str(repository),
                    target_type=_as_str(structured.get("repository_entity_type")) or "Component",
                )
            )

        service = structured.get("service_id")
        database = structured.get("database_id")
        if service and database:
            relations.append(
                ExtractedGraphRelation(
                    source=str(service),
                    source_type=_as_str(structured.get("service_entity_type")) or "Component",
                    relation="DEPENDS_ON",
                    target=str(database),
                    target_type=_as_str(structured.get("database_entity_type")) or "Technology",
                )
            )

    if isinstance(metadata, dict):
        author = metadata.get("author_id") or metadata.get("user_id")
        repository = metadata.get("repository_id") or metadata.get("repo_id")
        if author and repository:
            relations.append(
                ExtractedGraphRelation(
                    source=str(author),
                    source_type="Person",
                    relation="WORKS_ON",
                    target=str(repository),
                    target_type="Component",
                )
            )
    return relations


async def validate_relations(
    registry: GraphSchemaRegistry,
    *,
    namespace_id: str,
    project_id: str | None,
    routes: list[DomainRoute],
    relations: list[ExtractedGraphRelation],
) -> list[ValidatedGraphRelation]:
    packs = [route.pack for route in routes] or await registry.list_active_packs(
        namespace_id=namespace_id,
        project_id=project_id,
    )
    validated: list[ValidatedGraphRelation] = []
    for relation in relations:
        item = _validate_relation(relation=relation, packs=packs)
        if item is None:
            continue
        validated.append(item)
        if item.domain_type is not None and item.domain_type.startswith("unknown:"):
            await registry.record_schema_candidate(
                namespace_id=namespace_id,
                domain="unknown",
                candidate_type=item.domain_type.split(":", 1)[-1],
                candidate_kind="node_type",
                fallback_type=item.source_type,
                example={
                    "source": relation.source,
                    "relation": relation.relation,
                    "target": relation.target,
                },
            )
    return validated


async def prepare_relations(
    registry: GraphSchemaRegistry,
    *,
    memory: CanonicalMemory,
    model_relations: list[ExtractedGraphRelation],
    episode: Episode | None = None,
) -> tuple[list[DomainRoute], list[ValidatedGraphRelation]]:
    routes = await route_for_memory(registry, memory)
    structured = extract_structured_relations(memory=memory, episode=episode)
    merged = _merge_relations(structured, model_relations)
    validated = await validate_relations(
        registry,
        namespace_id=memory.identity.namespace_id,
        project_id=memory.identity.project_id,
        routes=routes,
        relations=merged,
    )
    return routes, validated


def functional_relations_for_routes(routes: list[DomainRoute]) -> frozenset[str]:
    names: set[str] = set()
    for route in routes:
        names |= route.pack.functional_relations
    return frozenset(names)


def schema_version_label(routes: list[DomainRoute]) -> str:
    if not routes:
        return "core@1.0"
    return routes[0].pack.version_label


def _validate_relation(
    *,
    relation: ExtractedGraphRelation,
    packs: list[GraphSchemaPack],
) -> ValidatedGraphRelation | None:
    source_type, source_domain = _resolve_type(declared=relation.source_type, packs=packs)
    target_type, target_domain = _resolve_type(declared=relation.target_type, packs=packs)
    relation_name = _resolve_relation(relation.relation, packs=packs)
    if relation_name is None:
        return None

    if any(
        pack.allows_pattern(source=source_type, relation=relation_name, target=target_type)
        for pack in packs
    ):
        return ValidatedGraphRelation(
            source=relation.source,
            source_type=source_type,
            relation=relation_name,
            target=relation.target,
            target_type=target_type,
            domain_type=source_domain or target_domain,
        )

    if any(pack.allows_weak_relation(relation_name) for pack in packs):
        return ValidatedGraphRelation(
            source=relation.source,
            source_type=source_type,
            relation=relation_name,
            target=relation.target,
            target_type=target_type,
            is_weak=True,
            domain_type=source_domain or target_domain,
        )

    if relation_name == "RELATED_TO":
        return ValidatedGraphRelation(
            source=relation.source,
            source_type=source_type,
            relation=relation_name,
            target=relation.target,
            target_type=target_type,
            is_weak=True,
        )
    return None


def _resolve_type(
    *,
    declared: str | None,
    packs: list[GraphSchemaPack],
) -> tuple[str, str | None]:
    if declared is None:
        return "Concept", None
    normalized = declared.strip()
    if not normalized:
        return "Concept", None
    for pack in packs:
        alias = pack.type_aliases.get(normalized)
        if alias is not None:
            return alias, None
        if pack.allows_node_type(normalized):
            if pack.domain == "core":
                return normalized, None
            return "Component" if normalized in {"Service", "Repository"} else normalized, (
                f"{pack.domain}:{normalized}"
            )
    if normalized in {
        "Person",
        "Project",
        "Organization",
        "Technology",
        "Component",
        "Concept",
        "Task",
    }:
        return normalized, None
    return "UnknownEntity", f"unknown:{normalized}"


def _resolve_relation(relation: str, *, packs: list[GraphSchemaPack]) -> str | None:
    normalized = relation.strip().upper().replace(" ", "_")
    if not normalized:
        return None
    for pack in packs:
        alias = pack.relation_aliases.get(normalized)
        if alias is not None:
            return alias
    if normalized in _KNOWN_RELATIONS:
        return normalized
    return None


def _merge_relations(
    structured: list[ExtractedGraphRelation],
    model_relations: list[ExtractedGraphRelation],
) -> list[ExtractedGraphRelation]:
    merged: list[ExtractedGraphRelation] = []
    seen: set[tuple[str, str, str, str]] = set()
    for relation in [*structured, *model_relations]:
        key = (
            relation.source.casefold(),
            relation.relation.upper(),
            relation.target.casefold(),
            (relation.source_type or "").casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(relation)
    return merged


def _as_str(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
