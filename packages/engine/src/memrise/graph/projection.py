from memrise.core.enums import MemoryStatus
from memrise.core.graph import (
    GraphClaim,
    GraphClaimPersistenceResult,
    GraphEdgeCandidate,
    GraphNodeCandidate,
    GraphProjection,
    GraphRebuildResult,
)
from memrise.core.models import CanonicalMemory
from memrise.core.time import utc_now
from memrise.graph.entities import (
    EntityMention,
    EntityResolver,
    GraphEndpointRole,
    resolve_graph_node_type,
)
from memrise.graph.identity import stable_claim_id
from memrise.graph.schema import (
    ValidatedGraphRelation,
    functional_relations_for_routes,
    prepare_relations,
    schema_version_label,
)
from memrise.graph.types import coerce_relation, normalize_entity_name
from memrise.ports.graph_repository import GraphRepository
from memrise.ports.graph_store import GraphClaimStore
from memrise.ports.providers import ExtractedGraphRelation
from memrise.ports.repositories import MemoryStore
from memrise.ports.schema_registry import GraphSchemaRegistry

DEFAULT_SCHEMA_VERSION = "core@1.0"


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
        relation_type = coerce_relation(relation.relation)
        endpoint_specs: tuple[tuple[str, str | None, GraphEndpointRole], ...] = (
            (relation.source, relation.source_type, "source"),
            (relation.target, relation.target_type, "target"),
        )
        for temporary_id, declared_type, role in endpoint_specs:
            if temporary_id not in node_candidates:
                node_type = resolve_graph_node_type(
                    name=temporary_id,
                    declared_type=declared_type,
                    memory=memory,
                    role=role,
                )
                node_candidates[temporary_id] = GraphNodeCandidate(
                    temporary_id=temporary_id,
                    node_type=node_type,
                    name=temporary_id.strip(),
                )
        edge_candidates.append(
            GraphEdgeCandidate(
                source=relation.source,
                relation=relation_type,
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


def build_graph_projection_from_claims(
    *,
    memory: CanonicalMemory,
    persisted: GraphClaimPersistenceResult,
    projection: GraphProjection,
) -> GraphProjection:
    entity_name_by_id = {entity.id: entity.canonical_name for entity in persisted.entities}
    temp_id_by_entity_id = {
        entity.id: candidate.temporary_id
        for entity, candidate in zip(persisted.entities, projection.nodes, strict=True)
    }

    nodes = tuple(
        GraphNodeCandidate(
            temporary_id=temp_id_by_entity_id[entity.id],
            node_type=entity.core_type,
            name=entity.canonical_name,
        )
        for entity in persisted.entities
    )
    edges = tuple(
        GraphEdgeCandidate(
            source=temp_id_by_entity_id.get(
                claim.subject_entity_id,
                entity_name_by_id.get(claim.subject_entity_id, claim.subject_entity_id),
            ),
            relation=claim.predicate,
            target=temp_id_by_entity_id.get(
                claim.object_entity_id,
                entity_name_by_id.get(claim.object_entity_id, claim.object_entity_id),
            ),
            claim_id=claim.id,
            usefulness_score=claim.usefulness_score,
        )
        for claim in persisted.claims
    )
    return GraphProjection(
        memory_version_id=memory.version.id,
        namespace_id=memory.identity.namespace_id,
        confidence=memory.version.confidence,
        valid_from=memory.version.valid_from,
        supersedes_version_id=memory.version.supersedes_version_id,
        nodes=nodes,
        edges=edges,
    )


def build_projection_from_active_claims(
    *,
    memory: CanonicalMemory,
    claims: list[GraphClaim],
    entity_name_by_id: dict[str, str],
    entity_type_by_id: dict[str, str],
) -> GraphProjection | None:
    if not claims:
        return None
    node_candidates: dict[str, GraphNodeCandidate] = {}
    edge_candidates: list[GraphEdgeCandidate] = []
    for claim in claims:
        for entity_id in (claim.subject_entity_id, claim.object_entity_id):
            name = entity_name_by_id.get(entity_id)
            core_type = entity_type_by_id.get(entity_id)
            if name is None or core_type is None:
                continue
            if entity_id not in node_candidates:
                node_candidates[entity_id] = GraphNodeCandidate(
                    temporary_id=entity_id,
                    node_type=core_type,
                    name=name,
                )
        source = node_candidates.get(claim.subject_entity_id)
        target = node_candidates.get(claim.object_entity_id)
        if source is None or target is None:
            continue
        edge_candidates.append(
            GraphEdgeCandidate(
                source=source.temporary_id,
                relation=claim.predicate,
                target=target.temporary_id,
                claim_id=claim.id,
                usefulness_score=claim.usefulness_score,
            )
        )
    if not edge_candidates:
        return None
    return GraphProjection(
        memory_version_id=memory.version.id,
        namespace_id=memory.identity.namespace_id,
        confidence=memory.version.confidence,
        valid_from=memory.version.valid_from,
        supersedes_version_id=memory.version.supersedes_version_id,
        nodes=tuple(node_candidates.values()),
        edges=tuple(edge_candidates),
    )


async def persist_graph_claims(
    *,
    store: GraphClaimStore,
    entity_resolver: EntityResolver,
    memory: CanonicalMemory,
    projection: GraphProjection,
    validated_relations: list[ValidatedGraphRelation],
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    extractor_version: str | None = None,
    functional_relations: frozenset[str] = frozenset(),
) -> GraphClaimPersistenceResult:
    extracted_at = utc_now()

    entity_by_temp_id: dict[str, str] = {}
    entities = []
    for candidate in projection.nodes:
        resolution = await entity_resolver.resolve(
            mention=EntityMention(name=candidate.name, type_hint=candidate.node_type),
            namespace_id=projection.namespace_id,
            core_type=candidate.node_type,
            user_id=memory.identity.user_id,
            project_id=memory.identity.project_id,
        )
        if resolution.status == "ambiguous":
            await store.record_ambiguous_mention(
                namespace_id=projection.namespace_id,
                name=candidate.name,
                core_type=candidate.node_type,
                memory_version_id=projection.memory_version_id,
                candidate_entity_ids=resolution.candidates,
            )
            continue
        if resolution.status == "rejected" or resolution.entity_id is None:
            continue
        entity = await store.upsert_entity(
            entity_id=resolution.entity_id,
            namespace_id=projection.namespace_id,
            core_type=resolution.core_type or candidate.node_type,
            canonical_name=resolution.canonical_name or candidate.name.strip(),
            normalized_name=normalize_entity_name(candidate.name),
            aliases=(candidate.name.strip(),),
            user_id=memory.identity.user_id,
            project_id=memory.identity.project_id,
        )
        entity_by_temp_id[candidate.temporary_id] = entity.id
        entities.append(entity)

    evidence_text = memory.version.content
    claims: list[GraphClaim] = []
    for relation in validated_relations:
        subject_entity_id = entity_by_temp_id.get(relation.source)
        object_entity_id = entity_by_temp_id.get(relation.target)
        if subject_entity_id is None or object_entity_id is None:
            continue
        if relation.is_weak and relation.relation not in {
            "CO_OCCURS_WITH",
            "MENTIONED_WITH",
            "POSSIBLY_RELATED",
            "RELATED_TO",
        }:
            continue
        claim = await store.insert_claim_if_absent(
            claim_id=stable_claim_id(
                subject_entity_id=subject_entity_id,
                predicate=relation.relation,
                object_entity_id=object_entity_id,
                memory_version_id=projection.memory_version_id,
            ),
            namespace_id=projection.namespace_id,
            subject_entity_id=subject_entity_id,
            predicate=relation.relation,
            object_entity_id=object_entity_id,
            supporting_memory_version_id=projection.memory_version_id,
            evidence_text=evidence_text,
            confidence=projection.confidence,
            valid_from=projection.valid_from,
            schema_version=schema_version,
            extractor_version=extractor_version,
            extracted_at=extracted_at,
        )
        claims.append(claim)

        if memory.version.status == MemoryStatus.CONTESTED:
            conflicts = await store.list_conflicting_active_claims(
                namespace_id=projection.namespace_id,
                subject_entity_id=subject_entity_id,
                predicate=relation.relation,
                object_entity_id=object_entity_id,
                excluding_memory_version_id=projection.memory_version_id,
            )
            if conflicts:
                await store.mark_claims_contradicted(
                    namespace_id=projection.namespace_id,
                    claim_ids=[item.id for item in conflicts],
                )

        if relation.relation in functional_relations:
            rivals = [
                rival
                for rival in await store.list_active_claims_by_subject_predicate(
                    namespace_id=projection.namespace_id,
                    subject_entity_id=subject_entity_id,
                    predicate=relation.relation,
                )
                if rival.object_entity_id != object_entity_id
                and rival.supporting_memory_version_id != projection.memory_version_id
            ]
            if rivals:
                rival_ids = [rival.id for rival in rivals]
                if memory.version.status == MemoryStatus.CONTESTED:
                    await store.mark_claims_contradicted(
                        namespace_id=projection.namespace_id,
                        claim_ids=rival_ids,
                    )
                else:
                    # Single-valued predicate: the newest active statement wins.
                    await store.supersede_claims_by_ids(
                        namespace_id=projection.namespace_id,
                        claim_ids=rival_ids,
                        valid_until=extracted_at,
                        superseded_by_claim_id=claim.id,
                    )

    superseded_by_map: dict[str, str] = {}
    if projection.supersedes_version_id is not None and claims:
        old_claims = await store.list_active_claims(
            namespace_id=projection.namespace_id,
            memory_version_id=projection.supersedes_version_id,
        )
        for old_claim in old_claims:
            for new_claim in claims:
                if (
                    old_claim.subject_entity_id == new_claim.subject_entity_id
                    and old_claim.predicate == new_claim.predicate
                    and old_claim.object_entity_id == new_claim.object_entity_id
                ):
                    superseded_by_map[old_claim.id] = new_claim.id

    superseded_claim_count = 0
    if projection.supersedes_version_id is not None:
        superseded_claim_count = await store.supersede_claims_for_memory_version(
            namespace_id=projection.namespace_id,
            memory_version_id=projection.supersedes_version_id,
            valid_until=projection.valid_from,
            superseded_by_claim_ids=superseded_by_map or None,
        )

    return GraphClaimPersistenceResult(
        memory_version_id=projection.memory_version_id,
        namespace_id=projection.namespace_id,
        entities=tuple(entities),
        claims=tuple(claims),
        superseded_claim_count=superseded_claim_count,
    )


class GraphProjectionService:
    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        graph_claim_store: GraphClaimStore,
        schema_registry: GraphSchemaRegistry,
        min_confidence: float = 0.5,
    ) -> None:
        self._graph_repository = graph_repository
        self._graph_claim_store = graph_claim_store
        self._schema_registry = schema_registry
        self._entity_resolver = EntityResolver(claim_store=graph_claim_store)
        self._min_confidence = min_confidence

    async def project_memory(
        self,
        *,
        memory: CanonicalMemory,
        relations: list[ExtractedGraphRelation],
        extractor_version: str | None = None,
    ):
        routes, validated = await prepare_relations(
            self._schema_registry,
            memory=memory,
            model_relations=relations,
        )
        if not validated:
            return None
        projection = build_graph_projection(
            memory=memory,
            relations=[
                ExtractedGraphRelation(
                    source=item.source,
                    source_type=item.source_type,
                    relation=item.relation,
                    target=item.target,
                    target_type=item.target_type,
                )
                for item in validated
            ],
            min_confidence=self._min_confidence,
        )
        if projection is None:
            return None
        persisted = await persist_graph_claims(
            store=self._graph_claim_store,
            entity_resolver=self._entity_resolver,
            memory=memory,
            projection=projection,
            validated_relations=validated,
            schema_version=schema_version_label(routes),
            extractor_version=extractor_version,
            functional_relations=functional_relations_for_routes(routes),
        )
        age_projection = build_graph_projection_from_claims(
            memory=memory,
            persisted=persisted,
            projection=projection,
        )
        return await self._project_to_age(age_projection)

    async def project_from_claims(
        self,
        *,
        memory: CanonicalMemory,
        projection: GraphProjection,
    ):
        return await self._project_to_age(projection)

    async def _project_to_age(self, projection: GraphProjection):
        if not await self._graph_repository.is_available():
            msg = "apache age is unavailable for graph projection"
            raise RuntimeError(msg)
        return await self._graph_repository.project(projection)


class GraphRebuildService:
    def __init__(
        self,
        *,
        claim_store: GraphClaimStore,
        memory_store: MemoryStore,
        graph_projection: GraphProjectionService,
    ) -> None:
        self._claim_store = claim_store
        self._memory_store = memory_store
        self._graph_projection = graph_projection

    async def rebuild_namespace(self, namespace_id: str) -> GraphRebuildResult:
        claims = await self._claim_store.list_active_claims(namespace_id=namespace_id)
        if not claims:
            return GraphRebuildResult(
                namespace_id=namespace_id,
                projected_memory_version_count=0,
                projected_claim_count=0,
            )

        entity_ids = {
            entity_id
            for claim in claims
            for entity_id in (claim.subject_entity_id, claim.object_entity_id)
        }
        entity_name_by_id: dict[str, str] = {}
        entity_type_by_id: dict[str, str] = {}
        for entity_id in entity_ids:
            entity = await self._claim_store.get_entity_by_id(entity_id)
            if entity is None:
                continue
            entity_name_by_id[entity_id] = entity.canonical_name
            entity_type_by_id[entity_id] = entity.core_type

        claims_by_memory_version: dict[str, list[GraphClaim]] = {}
        for claim in claims:
            claims_by_memory_version.setdefault(claim.supporting_memory_version_id, []).append(
                claim
            )

        projected_memory_version_count = 0
        projected_claim_count = 0
        for memory_version_id, version_claims in claims_by_memory_version.items():
            memory = await self._memory_store.get_memory_version_by_id(memory_version_id)
            if memory is None:
                continue
            projection = build_projection_from_active_claims(
                memory=memory,
                claims=version_claims,
                entity_name_by_id=entity_name_by_id,
                entity_type_by_id=entity_type_by_id,
            )
            if projection is None:
                continue
            await self._graph_projection.project_from_claims(
                memory=memory,
                projection=projection,
            )
            projected_memory_version_count += 1
            projected_claim_count += len(version_claims)

        return GraphRebuildResult(
            namespace_id=namespace_id,
            projected_memory_version_count=projected_memory_version_count,
            projected_claim_count=projected_claim_count,
        )
