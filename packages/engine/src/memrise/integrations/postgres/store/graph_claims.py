import hashlib
from datetime import datetime

from sqlalchemy import exists, func, or_, select
from sqlalchemy import update as sa_update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.enums import GraphClaimStatus
from memrise.core.graph import GraphClaim, GraphEntity
from memrise.core.time import utc_now
from memrise.graph.types import normalize_entity_name
from memrise.integrations.postgres.schema.models import (
    GraphClaimRow,
    GraphEntityMentionRow,
    GraphEntityRow,
)
from memrise.integrations.postgres.session import session_scope


def _entity_from_row(row: GraphEntityRow) -> GraphEntity:
    return GraphEntity(
        id=row.id,
        namespace_id=row.namespace_id,
        core_type=row.core_type,
        domain_type=row.domain_type,
        canonical_name=row.canonical_name,
        normalized_name=row.normalized_name,
        aliases=tuple(row.aliases or ()),
        stable_source_id=row.stable_source_id,
        user_id=row.user_id,
        project_id=row.project_id,
        created_at=row.created_at,
    )


def _claim_from_row(row: GraphClaimRow) -> GraphClaim:
    return GraphClaim(
        id=row.id,
        namespace_id=row.namespace_id,
        subject_entity_id=row.subject_entity_id,
        predicate=row.predicate,
        object_entity_id=row.object_entity_id,
        supporting_memory_version_id=row.supporting_memory_version_id,
        evidence_text=row.evidence_text,
        confidence=row.confidence,
        usefulness_score=row.usefulness_score,
        status=GraphClaimStatus(row.status),
        valid_from=row.valid_from,
        valid_until=row.valid_until,
        superseded_by_claim_id=row.superseded_by_claim_id,
        schema_version=row.schema_version,
        extractor_version=row.extractor_version,
        extracted_at=row.extracted_at,
    )


def merge_aliases(existing: list[str] | None, incoming: tuple[str, ...]) -> list[str]:
    """Union alias lists, preserving first-seen order and skipping blanks."""
    merged: dict[str, str] = {}
    for alias in [*(existing or []), *incoming]:
        cleaned = alias.strip()
        if not cleaned:
            continue
        merged.setdefault(normalize_entity_name(cleaned), cleaned)
    return list(merged.values())


class PostgresGraphClaimStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record_ambiguous_mention(
        self,
        *,
        namespace_id: str,
        name: str,
        core_type: str,
        memory_version_id: str,
        candidate_entity_ids: tuple[str, ...],
    ) -> None:
        digest = hashlib.sha256(
            f"{namespace_id}:{core_type}:{normalize_entity_name(name)}:{memory_version_id}".encode()
        ).hexdigest()[:24]
        async with session_scope(self._session_factory) as session:
            await session.execute(
                insert(GraphEntityMentionRow)
                .values(
                    id=f"gmen-{digest}",
                    namespace_id=namespace_id,
                    name=name.strip(),
                    normalized_name=normalize_entity_name(name),
                    core_type=core_type,
                    memory_version_id=memory_version_id,
                    candidate_entity_ids=list(candidate_entity_ids),
                    status="ambiguous",
                    created_at=utc_now(),
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )

    async def merge_entities(
        self,
        *,
        namespace_id: str,
        source_entity_id: str,
        target_entity_id: str,
    ) -> int:
        if source_entity_id == target_entity_id:
            return 0
        async with session_scope(self._session_factory) as session:
            source = await session.get(GraphEntityRow, source_entity_id)
            target = await session.get(GraphEntityRow, target_entity_id)
            if source is None or target is None:
                return 0
            if source.namespace_id != namespace_id or target.namespace_id != namespace_id:
                return 0
            moved = 0
            for column in (GraphClaimRow.subject_entity_id, GraphClaimRow.object_entity_id):
                result = await session.execute(
                    sa_update(GraphClaimRow)
                    .where(
                        GraphClaimRow.namespace_id == namespace_id,
                        column == source_entity_id,
                    )
                    .values({column.key: target_entity_id})
                )
                moved += int(getattr(result, "rowcount", 0) or 0)
            target.aliases = merge_aliases(
                target.aliases,
                (source.canonical_name, *tuple(source.aliases or ())),
            )
            if target.stable_source_id is None and source.stable_source_id is not None:
                target.stable_source_id = source.stable_source_id
            await session.delete(source)
            return moved

    async def upsert_entity(
        self,
        *,
        entity_id: str,
        namespace_id: str,
        core_type: str,
        canonical_name: str,
        normalized_name: str,
        aliases: tuple[str, ...] = (),
        domain_type: str | None = None,
        stable_source_id: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> GraphEntity:
        now = utc_now()
        async with session_scope(self._session_factory) as session:
            await session.execute(
                insert(GraphEntityRow)
                .values(
                    id=entity_id,
                    namespace_id=namespace_id,
                    core_type=core_type,
                    domain_type=domain_type,
                    canonical_name=canonical_name,
                    normalized_name=normalized_name,
                    aliases=list(aliases),
                    stable_source_id=stable_source_id,
                    user_id=user_id,
                    project_id=project_id,
                    created_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=["namespace_id", "core_type", "normalized_name"],
                )
            )
            row = (
                await session.scalars(
                    select(GraphEntityRow)
                    .where(
                        GraphEntityRow.namespace_id == namespace_id,
                        GraphEntityRow.core_type == core_type,
                        GraphEntityRow.normalized_name == normalized_name,
                    )
                    .with_for_update()
                )
            ).one()
            # Merge instead of overwrite: aliases accumulate across mentions, and
            # identity fields set by earlier mentions are never cleared by later
            # mentions that omit them.
            row.canonical_name = canonical_name
            row.aliases = merge_aliases(row.aliases, aliases)
            if domain_type is not None:
                row.domain_type = domain_type
            if stable_source_id is not None:
                row.stable_source_id = stable_source_id
            if user_id is not None:
                row.user_id = user_id
            if project_id is not None:
                row.project_id = project_id
            return _entity_from_row(row)

    async def get_entity_by_identity(
        self,
        *,
        namespace_id: str,
        core_type: str,
        normalized_name: str,
    ) -> GraphEntity | None:
        async with self._session_factory() as session:
            row = (
                await session.scalars(
                    select(GraphEntityRow).where(
                        GraphEntityRow.namespace_id == namespace_id,
                        GraphEntityRow.core_type == core_type,
                        GraphEntityRow.normalized_name == normalized_name,
                    )
                )
            ).first()
            if row is None:
                return None
            return _entity_from_row(row)

    async def get_entity_by_id(self, entity_id: str) -> GraphEntity | None:
        async with self._session_factory() as session:
            row = (
                await session.scalars(select(GraphEntityRow).where(GraphEntityRow.id == entity_id))
            ).first()
            if row is None:
                return None
            return _entity_from_row(row)

    async def get_entity_by_stable_source_id(
        self,
        *,
        namespace_id: str,
        stable_source_id: str,
    ) -> GraphEntity | None:
        async with self._session_factory() as session:
            row = (
                await session.scalars(
                    select(GraphEntityRow).where(
                        GraphEntityRow.namespace_id == namespace_id,
                        GraphEntityRow.stable_source_id == stable_source_id,
                    )
                )
            ).first()
            if row is None:
                return None
            return _entity_from_row(row)

    async def find_entities_by_term(
        self,
        *,
        namespace_id: str,
        term: str,
        core_type: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
        limit: int = 5,
    ) -> list[GraphEntity]:
        stripped = term.strip()
        normalized = normalize_entity_name(stripped)
        pattern = f"%{stripped}%"
        alias_values = func.jsonb_array_elements_text(GraphEntityRow.aliases).table_valued(
            "alias_value"
        )
        async with self._session_factory() as session:
            filters = [GraphEntityRow.namespace_id == namespace_id]
            if core_type is not None:
                filters.append(GraphEntityRow.core_type == core_type)
            if user_id is not None:
                filters.append(
                    or_(GraphEntityRow.user_id.is_(None), GraphEntityRow.user_id == user_id)
                )
            if project_id is not None:
                filters.append(
                    or_(
                        GraphEntityRow.project_id.is_(None), GraphEntityRow.project_id == project_id
                    )
                )
            rows = (
                await session.scalars(
                    select(GraphEntityRow)
                    .where(
                        *filters,
                        or_(
                            GraphEntityRow.normalized_name == normalized,
                            GraphEntityRow.canonical_name.ilike(pattern),
                            exists(
                                select(1)
                                .select_from(alias_values)
                                .where(
                                    or_(
                                        func.lower(alias_values.c.alias_value) == normalized,
                                        alias_values.c.alias_value.ilike(pattern),
                                    )
                                )
                            ),
                        ),
                    )
                    .limit(limit)
                )
            ).all()
            return [_entity_from_row(row) for row in rows]

    async def insert_claim_if_absent(
        self,
        *,
        claim_id: str,
        namespace_id: str,
        subject_entity_id: str,
        predicate: str,
        object_entity_id: str,
        supporting_memory_version_id: str,
        evidence_text: str | None,
        confidence: float,
        valid_from: datetime,
        schema_version: str,
        extractor_version: str | None,
        extracted_at: datetime,
    ) -> GraphClaim:
        async with session_scope(self._session_factory) as session:
            await session.execute(
                insert(GraphClaimRow)
                .values(
                    id=claim_id,
                    namespace_id=namespace_id,
                    subject_entity_id=subject_entity_id,
                    predicate=predicate,
                    object_entity_id=object_entity_id,
                    supporting_memory_version_id=supporting_memory_version_id,
                    evidence_text=evidence_text,
                    confidence=confidence,
                    usefulness_score=0.5,
                    status=GraphClaimStatus.ACTIVE.value,
                    valid_from=valid_from,
                    valid_until=None,
                    superseded_by_claim_id=None,
                    schema_version=schema_version,
                    extractor_version=extractor_version,
                    extracted_at=extracted_at,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        "subject_entity_id",
                        "predicate",
                        "object_entity_id",
                        "supporting_memory_version_id",
                    ]
                )
            )
            row = (
                await session.scalars(
                    select(GraphClaimRow).where(
                        GraphClaimRow.subject_entity_id == subject_entity_id,
                        GraphClaimRow.predicate == predicate,
                        GraphClaimRow.object_entity_id == object_entity_id,
                        GraphClaimRow.supporting_memory_version_id == supporting_memory_version_id,
                    )
                )
            ).one()
            return _claim_from_row(row)

    async def supersede_claims_for_memory_version(
        self,
        *,
        namespace_id: str,
        memory_version_id: str,
        valid_until: datetime,
        superseded_by_claim_ids: dict[str, str] | None = None,
    ) -> int:
        async with session_scope(self._session_factory) as session:
            rows = (
                await session.scalars(
                    select(GraphClaimRow).where(
                        GraphClaimRow.namespace_id == namespace_id,
                        GraphClaimRow.supporting_memory_version_id == memory_version_id,
                        GraphClaimRow.status == GraphClaimStatus.ACTIVE.value,
                    )
                )
            ).all()
            if not rows:
                return 0
            for row in rows:
                replacement_id = None
                if superseded_by_claim_ids is not None:
                    replacement_id = superseded_by_claim_ids.get(row.id)
                row.status = GraphClaimStatus.SUPERSEDED.value
                row.valid_until = valid_until
                if replacement_id is not None:
                    row.superseded_by_claim_id = replacement_id
            return len(rows)

    async def mark_claims_contradicted(
        self,
        *,
        namespace_id: str,
        claim_ids: list[str],
    ) -> int:
        if not claim_ids:
            return 0
        async with session_scope(self._session_factory) as session:
            rows = (
                await session.scalars(
                    select(GraphClaimRow).where(
                        GraphClaimRow.namespace_id == namespace_id,
                        GraphClaimRow.id.in_(claim_ids),
                        GraphClaimRow.status == GraphClaimStatus.ACTIVE.value,
                    )
                )
            ).all()
            for row in rows:
                row.status = GraphClaimStatus.CONTRADICTED.value
            return len(rows)

    async def update_claim_usefulness(self, *, claim_id: str, usefulness_score: float) -> None:
        async with session_scope(self._session_factory) as session:
            row = await session.get(GraphClaimRow, claim_id)
            if row is None:
                return
            row.usefulness_score = usefulness_score

    async def expire_due_claims(self, *, now: datetime) -> int:
        async with session_scope(self._session_factory) as session:
            rows = (
                await session.scalars(
                    select(GraphClaimRow).where(
                        GraphClaimRow.status == GraphClaimStatus.ACTIVE.value,
                        GraphClaimRow.valid_until.is_not(None),
                        GraphClaimRow.valid_until <= now,
                    )
                )
            ).all()
            for row in rows:
                row.status = GraphClaimStatus.EXPIRED.value
            return len(rows)

    async def list_conflicting_active_claims(
        self,
        *,
        namespace_id: str,
        subject_entity_id: str,
        predicate: str,
        object_entity_id: str,
        excluding_memory_version_id: str,
    ) -> list[GraphClaim]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(GraphClaimRow).where(
                        GraphClaimRow.namespace_id == namespace_id,
                        GraphClaimRow.subject_entity_id == subject_entity_id,
                        GraphClaimRow.predicate == predicate,
                        GraphClaimRow.object_entity_id == object_entity_id,
                        GraphClaimRow.supporting_memory_version_id != excluding_memory_version_id,
                        GraphClaimRow.status == GraphClaimStatus.ACTIVE.value,
                    )
                )
            ).all()
            return [_claim_from_row(row) for row in rows]

    async def list_active_claims(
        self,
        *,
        namespace_id: str,
        memory_version_id: str | None = None,
    ) -> list[GraphClaim]:
        filters = [
            GraphClaimRow.namespace_id == namespace_id,
            GraphClaimRow.status == GraphClaimStatus.ACTIVE.value,
        ]
        if memory_version_id is not None:
            filters.append(GraphClaimRow.supporting_memory_version_id == memory_version_id)
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(GraphClaimRow).where(*filters).order_by(GraphClaimRow.id)
                )
            ).all()
            return [_claim_from_row(row) for row in rows]
