from copy import deepcopy

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.enums import JobStatus, JobType, MemoryStatus
from memrise.core.models import (
    BackgroundJob,
    CanonicalMemory,
    Episode,
    Feedback,
    MemorySource,
    RetrievalItem,
    RetrievalTrace,
    Scope,
)
from memrise.core.text import normalize_lookup
from memrise.core.time import utc_now
from memrise.integrations.postgres.job_queue import PostgresJobQueue
from memrise.integrations.postgres.mappers import (
    canonical_from_rows,
    episode_from_row,
    retrieval_item_from_row,
    retrieval_trace_from_row,
)
from memrise.integrations.postgres.models import (
    EpisodeRow,
    GraphProjectionJobRow,
    JobRow,
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
from memrise.learning.reconciliation import Reconciler
from memrise.ports.ids import IdGenerator
from memrise.ports.providers import ExtractedGraphRelation, ExtractedMemoryCandidate


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

    async def save_episode(self, episode: Episode) -> None:
        async with session_scope(self._session_factory) as session:
            existing = await session.get(EpisodeRow, episode.id)
            if existing is not None:
                return
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
                    created_at=episode.created_at,
                )
            )

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
        filters = [
            MemoryRow.namespace_id == scope.namespace_id,
            MemoryRow.agent_id == scope.agent_id,
            MemoryVersionRow.status.in_(statuses),
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
    ) -> CanonicalMemory | None:
        now = utc_now()
        async with session_scope(self._session_factory) as session:
            existing = await self._find_current_memory_in_session(
                session,
                scope=scope,
                subject=candidate.subject,
                key=candidate.key,
                include_contested=True,
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
                return None
            if plan.reinforce is not None:
                reinforce = plan.reinforce
                await session.execute(
                    update(MemoryVersionRow)
                    .where(MemoryVersionRow.id == reinforce.version_id)
                    .values(
                        usefulness_score=reinforce.usefulness_score,
                        confidence=reinforce.confidence,
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
                return await self._find_current_memory_in_session(
                    session,
                    scope=scope,
                    subject=candidate.subject,
                    key=candidate.key,
                    include_contested=True,
                )

            new_version = plan.new_version
            if new_version is None:
                return None
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
                    return None
                if (
                    new_version.supersede_existing_version_id is not None
                    and new_version.supersede_existing_status is not None
                ):
                    await session.execute(
                        update(MemoryVersionRow)
                        .where(MemoryVersionRow.id == new_version.supersede_existing_version_id)
                        .values(status=new_version.supersede_existing_status.value)
                    )
            version_row = MemoryVersionRow(
                id=self._apply_service.new_version_id(),
                memory_id=memory_row.id,
                version_number=new_version.version_number,
                content=new_version.candidate.content,
                structured_value=dict(new_version.candidate.structured_value),
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
                    .values(superseded_by_version_id=version_row.id)
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
            return canonical_from_rows(memory_row, version_row)

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
                )
                .order_by(MemoryVersionRow.version_number.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return canonical_from_rows(row[0], row[1])
