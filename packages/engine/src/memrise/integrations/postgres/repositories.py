from collections.abc import Sequence
from copy import deepcopy
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.enums import (
    Criticality,
    EpisodeKind,
    GraphEdgeStatus,
    JobStatus,
    JobType,
    MemoryOperation,
    MemoryStatus,
    MemoryType,
    RetrievalSourceType,
)
from memrise.core.models import (
    BackgroundJob,
    CanonicalMemory,
    Episode,
    Feedback,
    GraphEdge,
    GraphNode,
    MemoryIdentity,
    MemorySource,
    MemoryVersion,
    RetrievalItem,
    RetrievalTrace,
    Scope,
)
from memrise.integrations.postgres.models import (
    EpisodeRow,
    GraphEdgeRow,
    GraphNodeRow,
    JobRow,
    MemoryRow,
    MemorySourceRow,
    MemoryVersionRow,
    RetrievalFeedbackRow,
    RetrievalItemRow,
    RetrievalTraceRow,
)
from memrise.integrations.postgres.session import session_scope
from memrise.ports.providers import ExtractedMemoryCandidate
from memrise.services.ids import UuidGenerator
from memrise.services.outcome_learning import DefaultFeedbackPolicy, clamp_usefulness
from memrise.services.reconciliation import Reconciler, normalize_lookup


class PostgresMemoryStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._ids = UuidGenerator()
        self._reconciler = Reconciler()
        self._feedback_policy = DefaultFeedbackPolicy()

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
            return _episode_from_row(row) if row else None

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
            return [_episode_from_row(row) for row in rows]

    async def list_active_memories(
        self,
        *,
        scope: Scope,
        include_contested: bool = False,
    ) -> list[CanonicalMemory]:
        statuses = [MemoryStatus.ACTIVE.value]
        if include_contested:
            statuses.append(MemoryStatus.CONTESTED.value)
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(MemoryRow, MemoryVersionRow)
                    .join(MemoryVersionRow, MemoryVersionRow.memory_id == MemoryRow.id)
                    .where(
                        MemoryRow.namespace_id == scope.namespace_id,
                        MemoryRow.agent_id == scope.agent_id,
                        or_(MemoryRow.user_id.is_(None), MemoryRow.user_id == scope.user_id),
                        or_(
                            MemoryRow.project_id.is_(None), MemoryRow.project_id == scope.project_id
                        ),
                        MemoryVersionRow.status.in_(statuses),
                    )
                )
            ).all()
            return [_canonical_from_rows(memory, version) for memory, version in rows]

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
            return [_canonical_from_rows(memory, version) for memory, version in rows]

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
        now = datetime.now(UTC)
        async with session_scope(self._session_factory) as session:
            existing = await self._find_current_memory_in_session(
                session,
                scope=scope,
                subject=candidate.subject,
                key=candidate.key,
                include_contested=True,
            )
            decision = self._reconciler.decide(candidate=candidate, existing=existing, now=now)
            if decision.operation == MemoryOperation.NOOP:
                return None
            if decision.operation == MemoryOperation.REINFORCE and existing is not None:
                await session.execute(
                    update(MemoryVersionRow)
                    .where(MemoryVersionRow.id == existing.version.id)
                    .values(
                        usefulness_score=clamp_usefulness(existing.version.usefulness_score + 0.03),
                        confidence=min(1.0, existing.version.confidence + 0.02),
                    )
                )
                for episode_id in source_episode_ids:
                    await session.merge(
                        MemorySourceRow(
                            memory_version_id=existing.version.id,
                            episode_id=episode_id,
                            relation="reinforced_by",
                        )
                    )
                refreshed = await self._find_current_memory_in_session(
                    session,
                    scope=scope,
                    subject=candidate.subject,
                    key=candidate.key,
                    include_contested=True,
                )
                return refreshed

            valid_until = (
                datetime.fromisoformat(candidate.valid_until).astimezone(UTC)
                if candidate.valid_until
                else None
            )
            if existing is None:
                memory_row = MemoryRow(
                    id=self._ids.new_id("mem"),
                    namespace_id=scope.namespace_id,
                    agent_id=scope.agent_id,
                    user_id=scope.user_id,
                    project_id=scope.project_id,
                    type=candidate.type.value,
                    subject=candidate.subject,
                    key=candidate.key,
                    normalized_subject=normalize_lookup(candidate.subject),
                    normalized_key=normalize_lookup(candidate.key),
                    created_at=now,
                )
                session.add(memory_row)
                await session.flush()
                version_number = 1
                supersedes_version_id = None
            else:
                memory_row = await session.get(MemoryRow, existing.identity.id)
                if memory_row is None:
                    return None
                version_number = existing.version.version_number + 1
                supersedes_version_id = existing.version.id
                old_status = (
                    MemoryStatus.CONTESTED
                    if decision.operation == MemoryOperation.CONTEST
                    else MemoryStatus.SUPERSEDED
                )
                await session.execute(
                    update(MemoryVersionRow)
                    .where(MemoryVersionRow.id == existing.version.id)
                    .values(status=old_status.value)
                )
            status = (
                MemoryStatus.CONTESTED
                if decision.operation == MemoryOperation.CONTEST
                else MemoryStatus.ACTIVE
            )
            version_row = MemoryVersionRow(
                id=self._ids.new_id("memv"),
                memory_id=memory_row.id,
                version_number=version_number,
                content=candidate.content,
                structured_value=dict(candidate.structured_value),
                status=status.value,
                confidence=candidate.confidence,
                importance=candidate.importance,
                criticality=candidate.criticality.value,
                usefulness_score=0.5,
                valid_from=now,
                valid_until=valid_until,
                supersedes_version_id=supersedes_version_id,
                embedding=embedding,
                created_at=now,
            )
            session.add(version_row)
            await session.flush()
            if supersedes_version_id:
                await session.execute(
                    update(MemoryVersionRow)
                    .where(MemoryVersionRow.id == supersedes_version_id)
                    .values(superseded_by_version_id=version_row.id)
                )
            for episode_id in source_episode_ids:
                session.add(
                    MemorySourceRow(
                        memory_version_id=version_row.id,
                        episode_id=episode_id,
                        relation="derived_from",
                    )
                )
            await session.flush()
            return _canonical_from_rows(memory_row, version_row)

    async def save_graph_projection(
        self,
        *,
        memory: CanonicalMemory,
        relations: list[tuple[str, str, str]],
    ) -> list[GraphEdge]:
        if memory.version.status != MemoryStatus.ACTIVE:
            return []
        async with session_scope(self._session_factory) as session:
            edges: list[GraphEdge] = []
            for source, relation, target in relations:
                source_node = await self._get_or_create_node(session, memory, source)
                target_node = await self._get_or_create_node(session, memory, target)
                edge_row = GraphEdgeRow(
                    id=self._ids.new_id("edge"),
                    source_node_id=source_node.id,
                    target_node_id=target_node.id,
                    relation=relation,
                    source_memory_version_id=memory.version.id,
                    status=GraphEdgeStatus.ACTIVE.value,
                    confidence=memory.version.confidence,
                    usefulness_score=memory.version.usefulness_score,
                    valid_from=memory.version.valid_from,
                    valid_until=memory.version.valid_until,
                )
                session.add(edge_row)
                await session.flush()
                edges.append(_graph_edge_from_row(edge_row))
            return edges

    async def list_graph_neighborhood(
        self,
        *,
        scope: Scope,
        query: str | None,
        hops: int,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        del hops
        terms = [term for term in normalize_lookup(query or "").split() if term]
        async with self._session_factory() as session:
            node_stmt = select(GraphNodeRow).where(GraphNodeRow.namespace_id == scope.namespace_id)
            if scope.project_id is not None:
                node_stmt = node_stmt.where(
                    or_(
                        GraphNodeRow.project_id.is_(None),
                        GraphNodeRow.project_id == scope.project_id,
                    )
                )
            if terms:
                node_stmt = node_stmt.where(
                    or_(*[GraphNodeRow.normalized_name.contains(term) for term in terms])
                )
            node_rows = (await session.scalars(node_stmt.limit(50))).all()
            node_ids = [node.id for node in node_rows]
            edge_rows: Sequence[GraphEdgeRow] = []
            if node_ids:
                edge_rows = (
                    await session.scalars(
                        select(GraphEdgeRow).where(
                            GraphEdgeRow.status == GraphEdgeStatus.ACTIVE.value,
                            or_(
                                GraphEdgeRow.source_node_id.in_(node_ids),
                                GraphEdgeRow.target_node_id.in_(node_ids),
                            ),
                        )
                    )
                ).all()
            return [_graph_node_from_row(row) for row in node_rows], [
                _graph_edge_from_row(row) for row in edge_rows
            ]

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
            delta = self._feedback_policy.usefulness_delta(feedback.outcome, feedback.confidence)
            score = clamp_usefulness(row.usefulness_score + delta)
            row.usefulness_score = score
            return score

    async def get_retrieval_items(self, retrieval_id: str) -> list[RetrievalItem]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(RetrievalItemRow).where(RetrievalItemRow.retrieval_id == retrieval_id)
                )
            ).all()
            return [_retrieval_item_from_row(row) for row in rows]

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
            return [_retrieval_trace_from_row(row) for row in rows]

    async def enqueue(
        self,
        *,
        job_type: JobType,
        payload: dict[str, object],
        dedupe_key: str | None = None,
    ) -> str:
        async with session_scope(self._session_factory) as session:
            if dedupe_key:
                existing = (
                    await session.scalars(select(JobRow).where(JobRow.dedupe_key == dedupe_key))
                ).first()
                if existing is not None:
                    return existing.id
            now = datetime.now(UTC)
            row = JobRow(
                id=self._ids.new_id("job"),
                type=job_type.value,
                payload=deepcopy(payload),
                status=JobStatus.PENDING.value,
                attempts=0,
                max_attempts=3,
                run_at=now,
                locked_at=None,
                locked_by=None,
                last_error=None,
                dedupe_key=dedupe_key,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            return row.id

    async def claim_next(self, *, worker_id: str) -> BackgroundJob | None:
        async with session_scope(self._session_factory) as session:
            now = datetime.now(UTC)
            row = (
                await session.scalars(
                    select(JobRow)
                    .where(
                        JobRow.status.in_([JobStatus.PENDING.value, JobStatus.RETRYABLE.value]),
                        JobRow.run_at <= now,
                    )
                    .order_by(JobRow.run_at, JobRow.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
            ).first()
            if row is None:
                return None
            row.status = JobStatus.RUNNING.value
            row.attempts += 1
            row.locked_by = worker_id
            row.locked_at = now
            row.updated_at = now
            return _job_from_row(row)

    async def complete(self, job_id: str) -> None:
        async with session_scope(self._session_factory) as session:
            row = await session.get(JobRow, job_id)
            if row is None:
                return
            row.status = JobStatus.COMPLETED.value
            row.locked_by = None
            row.locked_at = None
            row.updated_at = datetime.now(UTC)

    async def fail(self, job_id: str, error: str) -> None:
        async with session_scope(self._session_factory) as session:
            row = await session.get(JobRow, job_id)
            if row is None:
                return
            now = datetime.now(UTC)
            row.status = (
                JobStatus.FAILED.value
                if row.attempts >= row.max_attempts
                else JobStatus.RETRYABLE.value
            )
            row.locked_by = None
            row.locked_at = None
            row.last_error = error[:4000]
            row.run_at = now + timedelta(seconds=2 ** max(0, row.attempts - 1))
            row.updated_at = now

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
        return _canonical_from_rows(row[0], row[1])

    async def _get_or_create_node(
        self,
        session: AsyncSession,
        memory: CanonicalMemory,
        name: str,
    ) -> GraphNodeRow:
        normalized = normalize_lookup(name)
        row = (
            await session.scalars(
                select(GraphNodeRow).where(
                    GraphNodeRow.namespace_id == memory.identity.namespace_id,
                    GraphNodeRow.project_id.is_(memory.identity.project_id)
                    if memory.identity.project_id is None
                    else GraphNodeRow.project_id == memory.identity.project_id,
                    GraphNodeRow.normalized_name == normalized,
                )
            )
        ).first()
        if row is not None:
            return row
        row = GraphNodeRow(
            id=self._ids.new_id("node"),
            namespace_id=memory.identity.namespace_id,
            project_id=memory.identity.project_id,
            node_type="entity",
            canonical_name=name,
            normalized_name=normalized,
            aliases=[name],
            metadata_={},
        )
        session.add(row)
        await session.flush()
        return row


def _episode_from_row(row: EpisodeRow) -> Episode:
    return Episode(
        id=row.id,
        namespace_id=row.namespace_id,
        agent_id=row.agent_id,
        user_id=row.user_id,
        session_id=row.session_id,
        project_id=row.project_id,
        kind=EpisodeKind(row.kind),
        content=row.content,
        metadata=dict(row.metadata_),
        created_at=row.created_at,
    )


def _canonical_from_rows(memory: MemoryRow, version: MemoryVersionRow) -> CanonicalMemory:
    identity = MemoryIdentity(
        id=memory.id,
        namespace_id=memory.namespace_id,
        agent_id=memory.agent_id,
        user_id=memory.user_id,
        project_id=memory.project_id,
        type=MemoryType(memory.type),
        subject=memory.subject,
        key=memory.key,
        created_at=memory.created_at,
    )
    memory_version = MemoryVersion(
        id=version.id,
        memory_id=version.memory_id,
        version_number=version.version_number,
        content=version.content,
        structured_value=dict(version.structured_value),
        status=MemoryStatus(version.status),
        confidence=version.confidence,
        importance=version.importance,
        criticality=Criticality(version.criticality),
        usefulness_score=version.usefulness_score,
        valid_from=version.valid_from,
        valid_until=version.valid_until,
        supersedes_version_id=version.supersedes_version_id,
        superseded_by_version_id=version.superseded_by_version_id,
        created_at=version.created_at,
        embedding=list(version.embedding) if version.embedding is not None else None,
    )
    return CanonicalMemory(identity=identity, version=memory_version)


def _graph_node_from_row(row: GraphNodeRow) -> GraphNode:
    return GraphNode(
        id=row.id,
        namespace_id=row.namespace_id,
        project_id=row.project_id,
        node_type=row.node_type,
        canonical_name=row.canonical_name,
        normalized_name=row.normalized_name,
        aliases=list(row.aliases),
        metadata=dict(row.metadata_),
    )


def _graph_edge_from_row(row: GraphEdgeRow) -> GraphEdge:
    return GraphEdge(
        id=row.id,
        source_node_id=row.source_node_id,
        target_node_id=row.target_node_id,
        relation=row.relation,
        source_memory_version_id=row.source_memory_version_id,
        status=GraphEdgeStatus(row.status),
        confidence=row.confidence,
        usefulness_score=row.usefulness_score,
        valid_from=row.valid_from,
        valid_until=row.valid_until,
    )


def _retrieval_trace_from_row(row: RetrievalTraceRow) -> RetrievalTrace:
    return RetrievalTrace(
        id=row.id,
        namespace_id=row.namespace_id,
        agent_id=row.agent_id,
        query=row.query,
        task_type=row.task_type,
        project_id=row.project_id,
        token_budget=row.token_budget,
        created_at=row.created_at,
    )


def _retrieval_item_from_row(row: RetrievalItemRow) -> RetrievalItem:
    return RetrievalItem(
        retrieval_id=row.retrieval_id,
        memory_version_id=row.memory_version_id,
        graph_edge_id=row.graph_edge_id,
        source_type=RetrievalSourceType(row.source_type),
        original_rank=row.original_rank,
        final_rank=row.final_rank,
        lexical_score=row.lexical_score,
        semantic_score=row.semantic_score,
        graph_score=row.graph_score,
        usefulness_score=row.usefulness_score,
        selected_for_context=row.selected_for_context,
        token_count=row.token_count,
    )


def _job_from_row(row: JobRow) -> BackgroundJob:
    return BackgroundJob(
        id=row.id,
        type=JobType(row.type),
        payload=dict(row.payload),
        status=JobStatus(row.status),
        attempts=row.attempts,
        max_attempts=row.max_attempts,
        run_at=row.run_at,
        locked_at=row.locked_at,
        locked_by=row.locked_by,
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
