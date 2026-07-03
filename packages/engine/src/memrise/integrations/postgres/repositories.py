from copy import deepcopy

from sqlalchemy import case, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.enums import CandidateStageStatus, JobStatus, JobType, MemoryStatus
from memrise.core.errors import CandidateStageNotFoundError, IdempotencyConflictError
from memrise.core.models import (
    ApplyCandidateOutcome,
    BackgroundJob,
    CanonicalMemory,
    Episode,
    EpisodeSaveOutcome,
    Feedback,
    MemoryCandidateStage,
    MemorySource,
    RetrievalItem,
    RetrievalTrace,
    Scope,
)
from memrise.core.text import normalize_lookup
from memrise.core.time import utc_now
from memrise.integrations.postgres.job_queue import PostgresJobQueue
from memrise.integrations.postgres.mappers import (
    candidate_stage_from_row,
    canonical_from_rows,
    episode_from_row,
    retrieval_item_from_row,
    retrieval_trace_from_row,
)
from memrise.integrations.postgres.models import (
    EpisodeRow,
    GraphProjectionJobRow,
    JobRow,
    MemoryCandidateRow,
    MemoryRow,
    MemorySourceRow,
    MemoryVersionRow,
    RetrievalFeedbackRow,
    RetrievalItemRow,
    RetrievalTraceRow,
)
from memrise.integrations.postgres.session import session_scope
from memrise.learning.apply import MemoryApplyService
from memrise.learning.policy import DefaultFeedbackPolicy
from memrise.learning.reconciliation import (
    Reconciler,
    candidate_has_explicit_change,
    same_memory_value,
)
from memrise.ports.ids import IdGenerator
from memrise.ports.providers import ExtractedGraphRelation, ExtractedMemoryCandidate


def _episode_payload_matches(existing: Episode, incoming: Episode) -> bool:
    return (
        existing.kind == incoming.kind
        and existing.content == incoming.content
        and existing.agent_id == incoming.agent_id
        and existing.session_id == incoming.session_id
        and existing.user_id == incoming.user_id
        and existing.project_id == incoming.project_id
        and existing.metadata == incoming.metadata
    )


def _episode_insert_mapping(episode: Episode) -> dict[str, object]:
    return {
        "id": episode.id,
        "namespace_id": episode.namespace_id,
        "agent_id": episode.agent_id,
        "user_id": episode.user_id,
        "session_id": episode.session_id,
        "project_id": episode.project_id,
        "kind": episode.kind.value,
        "content": episode.content,
        "metadata_": deepcopy(episode.metadata),
        "idempotency_key": episode.idempotency_key,
        "created_at": episode.created_at,
    }


class PostgresMemoryStore:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        id_generator: IdGenerator,
    ) -> None:
        self._session_factory = session_factory
        self._ids = id_generator
        self._apply_service = MemoryApplyService(
            reconciler=Reconciler(),
            feedback_policy=DefaultFeedbackPolicy(),
            id_generator=id_generator,
        )
        self._jobs = PostgresJobQueue(session_factory, id_generator=id_generator)

    async def save_episode(self, episode: Episode) -> EpisodeSaveOutcome:
        async with session_scope(self._session_factory) as session:
            if episode.idempotency_key is not None:
                inserted_id = await session.scalar(
                    insert(EpisodeRow)
                    .values(_episode_insert_mapping(episode))
                    .on_conflict_do_nothing(
                        index_elements=["namespace_id", "idempotency_key"],
                        index_where=text("idempotency_key IS NOT NULL"),
                    )
                    .returning(EpisodeRow.id)
                )
                if inserted_id is not None:
                    return EpisodeSaveOutcome(episode=episode, created=True)
                existing = await session.scalar(
                    select(EpisodeRow).where(
                        EpisodeRow.namespace_id == episode.namespace_id,
                        EpisodeRow.idempotency_key == episode.idempotency_key,
                    )
                )
                if existing is None:
                    msg = (
                        "episode idempotency conflict could not be resolved for key "
                        f"{episode.idempotency_key!r}"
                    )
                    raise RuntimeError(msg)
                stored = episode_from_row(existing)
                if not _episode_payload_matches(stored, episode):
                    msg = (
                        "idempotency key already used with a different capture payload: "
                        f"{episode.idempotency_key!r}"
                    )
                    raise IdempotencyConflictError(msg)
                return EpisodeSaveOutcome(episode=stored, created=False)

            existing = await session.get(EpisodeRow, episode.id)
            if existing is not None:
                return EpisodeSaveOutcome(episode=episode_from_row(existing), created=False)
            session.add(
                EpisodeRow(
                    id=episode.id,
                    namespace_id=episode.namespace_id,
                    agent_id=episode.agent_id,
                    user_id=episode.user_id,
                    session_id=episode.session_id,
                    project_id=episode.project_id,
                    kind=episode.kind.value,
                    content=episode.content,
                    metadata_=deepcopy(episode.metadata),
                    idempotency_key=episode.idempotency_key,
                    created_at=episode.created_at,
                )
            )
            return EpisodeSaveOutcome(episode=episode, created=True)

    async def get_episode(self, episode_id: str) -> Episode | None:
        async with self._session_factory() as session:
            row = await session.get(EpisodeRow, episode_id)
            return episode_from_row(row) if row else None

    async def list_session_episodes(
        self,
        *,
        namespace_id: str,
        agent_id: str,
        session_id: str,
    ) -> list[Episode]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(EpisodeRow).where(
                        EpisodeRow.namespace_id == namespace_id,
                        EpisodeRow.agent_id == agent_id,
                        EpisodeRow.session_id == session_id,
                    )
                )
            ).all()
            return [episode_from_row(row) for row in rows]

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
            return await self._find_current_memory_in_session(
                session,
                scope=scope,
                subject=subject,
                key=key,
                include_contested=True,
            )

    async def apply_candidate(
        self,
        *,
        scope: Scope,
        candidate: ExtractedMemoryCandidate,
        source_episode_ids: list[str],
        embedding: list[float],
    ) -> ApplyCandidateOutcome:
        now = utc_now()
        async with session_scope(self._session_factory) as session:
            await self._lock_logical_memory_in_session(
                session,
                scope=scope,
                subject=candidate.subject,
                key=candidate.key,
            )
            existing = await self._find_current_memory_in_session(
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
                historical_duplicate = await self._find_matching_historical_memory_in_session(
                    session,
                    scope=scope,
                    candidate=candidate,
                )
                if historical_duplicate is not None:
                    return ApplyCandidateOutcome(
                        skip_reason="reconcile:historical_duplicate",
                    )
            if existing is None:
                existing = await self._find_latest_memory_in_session(
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
                memory = await self._find_current_memory_in_session(
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
                embedding=embedding,
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

    async def list_candidate_stages_for_episode(
        self, episode_id: str
    ) -> list[MemoryCandidateStage]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(MemoryCandidateRow)
                    .where(MemoryCandidateRow.episode_id == episode_id)
                    .order_by(MemoryCandidateRow.candidate_index)
                )
            ).all()
            return [candidate_stage_from_row(row) for row in rows]

    async def get_candidate_stage(self, candidate_stage_id: str) -> MemoryCandidateStage | None:
        async with self._session_factory() as session:
            row = await session.get(MemoryCandidateRow, candidate_stage_id)
            return candidate_stage_from_row(row) if row is not None else None

    async def save_candidate_stage(self, stage: MemoryCandidateStage) -> str:
        promoted = CandidateStageStatus.PROMOTED.value
        mapping = {
            "id": stage.id,
            "episode_id": stage.episode_id,
            "namespace_id": stage.namespace_id,
            "agent_id": stage.agent_id,
            "user_id": stage.user_id,
            "project_id": stage.project_id,
            "candidate_index": stage.candidate_index,
            "schema_version": stage.schema_version,
            "model_name": stage.model_name,
            "prompt_version": stage.prompt_version,
            "classification": deepcopy(stage.classification),
            "candidate": deepcopy(stage.candidate),
            "memory_type": stage.memory_type,
            "subject": stage.subject,
            "key": stage.key,
            "evidence_quote": stage.evidence_quote,
            "status": stage.status.value,
            "promotion_score": stage.promotion_score,
            "rejection_reason": stage.rejection_reason,
            "memory_version_id": stage.memory_version_id,
            "created_at": stage.created_at,
            "updated_at": stage.updated_at,
        }
        async with session_scope(self._session_factory) as session:
            inserted_id = await session.scalar(
                insert(MemoryCandidateRow)
                .values(mapping)
                .on_conflict_do_update(
                    index_elements=["episode_id", "candidate_index"],
                    set_={
                        "schema_version": stage.schema_version,
                        "model_name": stage.model_name,
                        "prompt_version": stage.prompt_version,
                        "classification": deepcopy(stage.classification),
                        "candidate": deepcopy(stage.candidate),
                        "memory_type": stage.memory_type,
                        "subject": stage.subject,
                        "key": stage.key,
                        "evidence_quote": stage.evidence_quote,
                        "promotion_score": stage.promotion_score,
                        "updated_at": stage.updated_at,
                        "status": case(
                            (
                                MemoryCandidateRow.status == promoted,
                                MemoryCandidateRow.status,
                            ),
                            else_=stage.status.value,
                        ),
                        "rejection_reason": case(
                            (
                                MemoryCandidateRow.status == promoted,
                                MemoryCandidateRow.rejection_reason,
                            ),
                            else_=stage.rejection_reason,
                        ),
                        "memory_version_id": case(
                            (
                                MemoryCandidateRow.status == promoted,
                                MemoryCandidateRow.memory_version_id,
                            ),
                            else_=stage.memory_version_id,
                        ),
                    },
                )
                .returning(MemoryCandidateRow.id)
            )
            if inserted_id is not None:
                return inserted_id
            existing = await session.scalar(
                select(MemoryCandidateRow.id).where(
                    MemoryCandidateRow.episode_id == stage.episode_id,
                    MemoryCandidateRow.candidate_index == stage.candidate_index,
                )
            )
            if existing is None:
                msg = (
                    "candidate stage conflict could not be resolved for episode "
                    f"{stage.episode_id!r} index {stage.candidate_index}"
                )
                raise RuntimeError(msg)
            return existing

    async def update_candidate_stage(
        self,
        candidate_stage_id: str,
        *,
        status: CandidateStageStatus,
        memory_version_id: str | None = None,
        rejection_reason: str | None = None,
    ) -> None:
        async with session_scope(self._session_factory) as session:
            row = await session.get(MemoryCandidateRow, candidate_stage_id)
            if row is None:
                raise CandidateStageNotFoundError(candidate_stage_id)
            row.status = status.value
            row.memory_version_id = memory_version_id
            row.rejection_reason = rejection_reason
            row.updated_at = utc_now()

    async def get_memory_version_by_id(self, memory_version_id: str) -> CanonicalMemory | None:
        async with self._session_factory() as session:
            version_row = await session.get(MemoryVersionRow, memory_version_id)
            if version_row is None:
                return None
            memory_row = await session.get(MemoryRow, version_row.memory_id)
            if memory_row is None:
                return None
            return canonical_from_rows(memory_row, version_row)

    async def schedule_graph_projection(
        self,
        *,
        memory: CanonicalMemory,
        relations: list[ExtractedGraphRelation],
    ) -> str | None:
        if memory.version.status != MemoryStatus.ACTIVE or not relations:
            return None
        dedupe_key = f"graph-projection:{memory.version.id}"
        async with session_scope(self._session_factory) as session:
            existing_job = (
                await session.scalars(select(JobRow).where(JobRow.dedupe_key == dedupe_key))
            ).first()
            if existing_job is not None:
                return existing_job.id
            now = utc_now()
            job_id = self._ids.new_id("job")
            session.add(
                JobRow(
                    id=job_id,
                    type=JobType.PROJECT_GRAPH.value,
                    payload={
                        "memory_version_id": memory.version.id,
                        "namespace_id": memory.identity.namespace_id,
                        "relations": [relation.model_dump() for relation in relations],
                    },
                    status=JobStatus.PENDING.value,
                    attempts=0,
                    max_attempts=5,
                    run_at=now,
                    dedupe_key=dedupe_key,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                GraphProjectionJobRow(
                    id=self._ids.new_id("gproj"),
                    namespace_id=memory.identity.namespace_id,
                    memory_version_id=memory.version.id,
                    status="pending",
                    attempts=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            return job_id

    async def save_retrieval_trace(
        self,
        trace: RetrievalTrace,
        items: list[RetrievalItem],
    ) -> None:
        async with session_scope(self._session_factory) as session:
            session.add(
                RetrievalTraceRow(
                    id=trace.id,
                    namespace_id=trace.namespace_id,
                    agent_id=trace.agent_id,
                    query=trace.query,
                    task_type=trace.task_type,
                    project_id=trace.project_id,
                    token_budget=trace.token_budget,
                    created_at=trace.created_at,
                )
            )
            await session.flush()
            for item in items:
                session.add(
                    RetrievalItemRow(
                        retrieval_id=item.retrieval_id,
                        memory_version_id=item.memory_version_id,
                        graph_edge_id=item.graph_edge_id,
                        source_type=item.source_type.value,
                        original_rank=item.original_rank,
                        final_rank=item.final_rank,
                        lexical_score=item.lexical_score,
                        semantic_score=item.semantic_score,
                        graph_score=item.graph_score,
                        usefulness_score=item.usefulness_score,
                        selected_for_context=item.selected_for_context,
                        token_count=item.token_count,
                    )
                )

    async def save_feedback(self, feedback: Feedback) -> float | None:
        async with session_scope(self._session_factory) as session:
            session.add(
                RetrievalFeedbackRow(
                    id=feedback.id,
                    retrieval_id=feedback.retrieval_id,
                    memory_version_id=feedback.memory_version_id,
                    graph_edge_id=feedback.graph_edge_id,
                    outcome=feedback.outcome.value,
                    source=feedback.source.value,
                    confidence=feedback.confidence,
                    task_type=feedback.task_type,
                    created_at=feedback.created_at,
                )
            )
            if feedback.memory_version_id is None:
                return None
            row = await session.get(MemoryVersionRow, feedback.memory_version_id)
            if row is None:
                return None
            score = self._apply_service.updated_usefulness_score(
                feedback=feedback,
                current_score=row.usefulness_score,
            )
            row.usefulness_score = score
            return score

    async def get_retrieval_items(self, retrieval_id: str) -> list[RetrievalItem]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(RetrievalItemRow).where(RetrievalItemRow.retrieval_id == retrieval_id)
                )
            ).all()
            return [retrieval_item_from_row(row) for row in rows]

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

    async def list_recent_retrievals(
        self, *, namespace_id: str, limit: int
    ) -> list[RetrievalTrace]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(RetrievalTraceRow)
                    .where(RetrievalTraceRow.namespace_id == namespace_id)
                    .order_by(RetrievalTraceRow.created_at.desc())
                    .limit(limit)
                )
            ).all()
            return [retrieval_trace_from_row(row) for row in rows]

    async def enqueue(
        self,
        *,
        job_type: JobType,
        payload: dict[str, object],
        dedupe_key: str | None = None,
    ) -> str:
        return await self._jobs.enqueue(
            job_type=job_type,
            payload=payload,
            dedupe_key=dedupe_key,
        )

    async def claim_next(self, *, worker_id: str) -> BackgroundJob | None:
        return await self._jobs.claim_next(worker_id=worker_id)

    async def get_job(self, job_id: str) -> BackgroundJob | None:
        return await self._jobs.get_job(job_id)

    async def find_job_id_by_dedupe_key(self, dedupe_key: str) -> str | None:
        return await self._jobs.find_job_id_by_dedupe_key(dedupe_key)

    async def complete(self, job_id: str) -> None:
        await self._jobs.complete(job_id)

    async def fail(self, job_id: str, error: str) -> None:
        await self._jobs.fail(job_id, error)

    async def _find_current_memory_in_session(
        self,
        session: AsyncSession,
        *,
        scope: Scope,
        subject: str,
        key: str,
        include_contested: bool,
    ) -> CanonicalMemory | None:
        statuses = [MemoryStatus.ACTIVE.value]
        if include_contested:
            statuses.append(MemoryStatus.CONTESTED.value)
        now = utc_now()
        row = (
            await session.execute(
                select(MemoryRow, MemoryVersionRow)
                .join(MemoryVersionRow, MemoryVersionRow.memory_id == MemoryRow.id)
                .where(
                    MemoryRow.namespace_id == scope.namespace_id,
                    MemoryRow.agent_id == scope.agent_id,
                    MemoryRow.user_id.is_(scope.user_id)
                    if scope.user_id is None
                    else MemoryRow.user_id == scope.user_id,
                    MemoryRow.project_id.is_(scope.project_id)
                    if scope.project_id is None
                    else MemoryRow.project_id == scope.project_id,
                    MemoryRow.normalized_subject == normalize_lookup(subject),
                    MemoryRow.normalized_key == normalize_lookup(key),
                    MemoryVersionRow.status.in_(statuses),
                    MemoryVersionRow.valid_from <= now,
                    or_(
                        MemoryVersionRow.valid_until.is_(None),
                        MemoryVersionRow.valid_until > now,
                    ),
                )
                .order_by(MemoryVersionRow.version_number.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return canonical_from_rows(row[0], row[1])

    async def _lock_logical_memory_in_session(
        self,
        session: AsyncSession,
        *,
        scope: Scope,
        subject: str,
        key: str,
    ) -> None:
        await session.execute(
            text("select pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {
                "lock_key": ":".join(
                    [
                        scope.namespace_id,
                        scope.agent_id,
                        scope.user_id or "",
                        scope.project_id or "",
                        normalize_lookup(subject),
                        normalize_lookup(key),
                    ]
                )
            },
        )

    async def _find_matching_historical_memory_in_session(
        self,
        session: AsyncSession,
        *,
        scope: Scope,
        candidate: ExtractedMemoryCandidate,
    ) -> CanonicalMemory | None:
        rows = (
            await session.execute(
                select(MemoryRow, MemoryVersionRow)
                .join(MemoryVersionRow, MemoryVersionRow.memory_id == MemoryRow.id)
                .where(
                    MemoryRow.namespace_id == scope.namespace_id,
                    MemoryRow.agent_id == scope.agent_id,
                    MemoryRow.user_id.is_(scope.user_id)
                    if scope.user_id is None
                    else MemoryRow.user_id == scope.user_id,
                    MemoryRow.project_id.is_(scope.project_id)
                    if scope.project_id is None
                    else MemoryRow.project_id == scope.project_id,
                    MemoryRow.normalized_subject == normalize_lookup(candidate.subject),
                    MemoryRow.normalized_key == normalize_lookup(candidate.key),
                    MemoryVersionRow.status.in_(
                        [
                            MemoryStatus.SUPERSEDED.value,
                            MemoryStatus.EXPIRED.value,
                            MemoryStatus.DELETED.value,
                        ]
                    ),
                )
                .order_by(MemoryVersionRow.version_number.desc())
            )
        ).all()
        for memory_row, version_row in rows:
            memory = canonical_from_rows(memory_row, version_row)
            if same_memory_value(memory, candidate):
                return memory
        return None

    async def _find_latest_memory_in_session(
        self,
        session: AsyncSession,
        *,
        scope: Scope,
        subject: str,
        key: str,
    ) -> CanonicalMemory | None:
        row = (
            await session.execute(
                select(MemoryRow, MemoryVersionRow)
                .join(MemoryVersionRow, MemoryVersionRow.memory_id == MemoryRow.id)
                .where(
                    MemoryRow.namespace_id == scope.namespace_id,
                    MemoryRow.agent_id == scope.agent_id,
                    MemoryRow.user_id.is_(scope.user_id)
                    if scope.user_id is None
                    else MemoryRow.user_id == scope.user_id,
                    MemoryRow.project_id.is_(scope.project_id)
                    if scope.project_id is None
                    else MemoryRow.project_id == scope.project_id,
                    MemoryRow.normalized_subject == normalize_lookup(subject),
                    MemoryRow.normalized_key == normalize_lookup(key),
                )
                .order_by(MemoryVersionRow.version_number.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return canonical_from_rows(row[0], row[1])
