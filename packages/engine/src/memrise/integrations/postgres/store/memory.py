from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.enums import MemoryStatus
from memrise.core.models import (
    ApplyCandidateOutcome,
    CanonicalMemory,
    MemorySource,
    Scope,
)
from memrise.core.text import normalize_lookup
from memrise.core.time import utc_now
from memrise.integrations.postgres.schema.mappers import canonical_from_rows
from memrise.integrations.postgres.schema.models import (
    MemoryRow,
    MemorySourceRow,
    MemoryVersionRow,
)
from memrise.integrations.postgres.session import session_scope
from memrise.integrations.postgres.store.queries import (
    find_current_memory_in_session,
    find_latest_memory_in_session,
    find_matching_historical_memory_in_session,
    find_semantic_duplicate_in_session,
    lock_logical_memory_in_session,
    search_lexical_in_session,
    search_semantic_in_session,
)
from memrise.learning.apply import MemoryApplyService
from memrise.learning.reconciliation import candidate_has_explicit_change, same_memory_value
from memrise.ports.providers import EmbeddingVector, ExtractedMemoryCandidate
from memrise.write.extraction_validation import embedding_text_for_candidate


class PostgresMemoryRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        apply_service: MemoryApplyService,
    ) -> None:
        self._session_factory = session_factory
        self._apply_service = apply_service

    async def list_active_memories(
        self,
        *,
        scope: Scope,
        include_contested: bool = False,
        user_id_is_wildcard: bool = False,
        project_id_is_wildcard: bool = False,
    ) -> list[CanonicalMemory]:
        statuses = [MemoryStatus.ACTIVE.value]
        if include_contested:
            statuses.append(MemoryStatus.CONTESTED.value)
        now = utc_now()
        filters = [
            MemoryRow.namespace_id == scope.namespace_id,
            MemoryRow.agent_id == scope.agent_id,
            MemoryVersionRow.status.in_(statuses),
            MemoryVersionRow.valid_from <= now,
            or_(MemoryVersionRow.valid_until.is_(None), MemoryVersionRow.valid_until > now),
        ]
        if not user_id_is_wildcard:
            filters.append(or_(MemoryRow.user_id.is_(None), MemoryRow.user_id == scope.user_id))
        if not project_id_is_wildcard:
            filters.append(
                or_(MemoryRow.project_id.is_(None), MemoryRow.project_id == scope.project_id)
            )
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(MemoryRow, MemoryVersionRow)
                    .join(MemoryVersionRow, MemoryVersionRow.memory_id == MemoryRow.id)
                    .where(*filters)
                )
            ).all()
            return [canonical_from_rows(memory, version) for memory, version in rows]

    async def search_lexical(
        self,
        *,
        scope: Scope,
        query: str,
        limit: int,
    ) -> list[tuple[CanonicalMemory, float]]:
        async with self._session_factory() as session:
            return await search_lexical_in_session(session, scope=scope, query=query, limit=limit)

    async def search_semantic(
        self,
        *,
        scope: Scope,
        embedding: EmbeddingVector,
        limit: int,
    ) -> list[tuple[CanonicalMemory, float]]:
        async with self._session_factory() as session:
            return await search_semantic_in_session(
                session, scope=scope, embedding=embedding, limit=limit
            )

    async def list_memory_history(self, memory_id: str) -> list[CanonicalMemory]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(MemoryRow, MemoryVersionRow)
                    .join(MemoryVersionRow, MemoryVersionRow.memory_id == MemoryRow.id)
                    .where(MemoryRow.id == memory_id)
                    .order_by(MemoryVersionRow.version_number)
                )
            ).all()
            return [canonical_from_rows(memory, version) for memory, version in rows]

    async def find_current_memory(
        self,
        *,
        scope: Scope,
        subject: str,
        key: str,
    ) -> CanonicalMemory | None:
        async with self._session_factory() as session:
            return await find_current_memory_in_session(
                session,
                scope=scope,
                subject=subject,
                key=key,
                include_contested=True,
            )

    async def get_memory_version_by_id(self, memory_version_id: str) -> CanonicalMemory | None:
        async with self._session_factory() as session:
            version_row = await session.get(MemoryVersionRow, memory_version_id)
            if version_row is None:
                return None
            memory_row = await session.get(MemoryRow, version_row.memory_id)
            if memory_row is None:
                return None
            return canonical_from_rows(memory_row, version_row)

    async def list_memory_sources(self, memory_version_id: str) -> list[MemorySource]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(MemorySourceRow).where(
                        MemorySourceRow.memory_version_id == memory_version_id
                    )
                )
            ).all()
            return [
                MemorySource(
                    memory_version_id=row.memory_version_id,
                    episode_id=row.episode_id,
                    relation=row.relation,
                )
                for row in rows
            ]

    async def apply_candidate(
        self,
        *,
        scope: Scope,
        candidate: ExtractedMemoryCandidate,
        source_episode_ids: list[str],
        embedding: EmbeddingVector,
    ) -> ApplyCandidateOutcome:
        now = utc_now()
        async with session_scope(self._session_factory) as session:
            await lock_logical_memory_in_session(
                session,
                scope=scope,
                subject=candidate.subject,
                key=candidate.key,
            )
            existing = await find_current_memory_in_session(
                session,
                scope=scope,
                subject=candidate.subject,
                key=candidate.key,
                include_contested=True,
            )
            if (
                existing is not None
                and not same_memory_value(existing, candidate)
                and not candidate_has_explicit_change(candidate)
            ):
                historical_duplicate = await find_matching_historical_memory_in_session(
                    session,
                    scope=scope,
                    candidate=candidate,
                )
                if historical_duplicate is not None:
                    return ApplyCandidateOutcome(
                        skip_reason="reconcile:historical_duplicate",
                    )
            if existing is None:
                existing = await find_semantic_duplicate_in_session(
                    session,
                    scope=scope,
                    subject=candidate.subject,
                    exclude_key=candidate.key,
                    embedding=embedding,
                )
            if existing is None:
                existing = await find_latest_memory_in_session(
                    session,
                    scope=scope,
                    subject=candidate.subject,
                    key=candidate.key,
                )
            plan = self._apply_service.plan_candidate(
                scope=scope,
                candidate=candidate,
                existing=existing,
                source_episode_ids=source_episode_ids,
                embedding=embedding,
                now=now,
            )
            if plan is None:
                return ApplyCandidateOutcome(
                    skip_reason=self._apply_service.noop_skip_reason(
                        candidate=candidate,
                        existing=existing,
                        now=now,
                    ),
                )
            if plan.reinforce is not None:
                reinforce = plan.reinforce
                await session.execute(
                    update(MemoryVersionRow)
                    .where(MemoryVersionRow.id == reinforce.version_id)
                    .values(
                        usefulness_score=reinforce.usefulness_score,
                        confidence=reinforce.confidence,
                        updated_at=now,
                    )
                )
                for episode_id in reinforce.source_episode_ids:
                    await session.merge(
                        MemorySourceRow(
                            memory_version_id=reinforce.version_id,
                            episode_id=episode_id,
                            relation="reinforced_by",
                        )
                    )
                memory = await find_current_memory_in_session(
                    session,
                    scope=scope,
                    subject=candidate.subject,
                    key=candidate.key,
                    include_contested=True,
                )
                return ApplyCandidateOutcome(memory=memory)

            new_version = plan.new_version
            if new_version is None:
                return ApplyCandidateOutcome(skip_reason="reconcile:noop")
            if existing is None:
                memory_row = MemoryRow(
                    id=new_version.memory_id,
                    namespace_id=scope.namespace_id,
                    agent_id=scope.agent_id,
                    user_id=scope.user_id,
                    project_id=scope.project_id,
                    type=new_version.candidate.type.value,
                    subject=new_version.candidate.subject,
                    key=new_version.candidate.key,
                    normalized_subject=normalize_lookup(new_version.candidate.subject),
                    normalized_key=normalize_lookup(new_version.candidate.key),
                    created_at=now,
                )
                session.add(memory_row)
                await session.flush()
            else:
                memory_row = await session.get(MemoryRow, existing.identity.id)
                if memory_row is None:
                    return ApplyCandidateOutcome(skip_reason="reconcile:deleted")
                if (
                    new_version.supersede_existing_version_id is not None
                    and new_version.supersede_existing_status is not None
                ):
                    lifecycle_values: dict[str, object] = {
                        "status": new_version.supersede_existing_status.value,
                        "updated_at": now,
                    }
                    if new_version.supersede_existing_status == MemoryStatus.SUPERSEDED:
                        lifecycle_values["valid_until"] = now
                    await session.execute(
                        update(MemoryVersionRow)
                        .where(MemoryVersionRow.id == new_version.supersede_existing_version_id)
                        .values(**lifecycle_values)
                    )
            version_row = MemoryVersionRow(
                id=self._apply_service.new_version_id(),
                memory_id=memory_row.id,
                version_number=new_version.version_number,
                content=new_version.candidate.content,
                structured_value=dict(new_version.candidate.structured_value),
                applicability=dict(new_version.candidate.applicability),
                status=new_version.new_version_status.value,
                confidence=new_version.candidate.confidence,
                importance=new_version.candidate.importance,
                criticality=new_version.candidate.criticality.value,
                usefulness_score=0.5,
                valid_from=now,
                valid_until=new_version.valid_until,
                supersedes_version_id=new_version.supersedes_version_id,
                embedding=embedding.values,
                embedding_model=embedding.model,
                embedding_dimensions=embedding.dimensions,
                embedding_text=embedding_text_for_candidate(new_version.candidate),
                search_text=new_version.candidate.search_text,
                created_at=now,
                updated_at=now,
            )
            session.add(version_row)
            await session.flush()
            if new_version.supersedes_version_id:
                await session.execute(
                    update(MemoryVersionRow)
                    .where(MemoryVersionRow.id == new_version.supersedes_version_id)
                    .values(superseded_by_version_id=version_row.id, updated_at=now)
                )
            for episode_id in new_version.source_episode_ids:
                session.add(
                    MemorySourceRow(
                        memory_version_id=version_row.id,
                        episode_id=episode_id,
                        relation="derived_from",
                    )
                )
            await session.flush()
            return ApplyCandidateOutcome(memory=canonical_from_rows(memory_row, version_row))
