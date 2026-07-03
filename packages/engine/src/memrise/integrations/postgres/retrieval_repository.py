from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.models import Feedback, RetrievalItem, RetrievalTrace
from memrise.integrations.postgres.mappers import (
    retrieval_item_from_row,
    retrieval_trace_from_row,
)
from memrise.integrations.postgres.models import (
    MemoryVersionRow,
    RetrievalFeedbackRow,
    RetrievalItemRow,
    RetrievalTraceRow,
)
from memrise.integrations.postgres.session import session_scope
from memrise.learning.apply import MemoryApplyService


class PostgresRetrievalRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        apply_service: MemoryApplyService,
    ) -> None:
        self._session_factory = session_factory
        self._apply_service = apply_service

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
