from copy import deepcopy

from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memrise.core.enums import CandidateStageStatus
from memrise.core.errors import CandidateStageNotFoundError
from memrise.core.models import MemoryCandidateStage
from memrise.core.time import utc_now
from memrise.integrations.postgres.schema.mappers import candidate_stage_from_row
from memrise.integrations.postgres.schema.models import MemoryCandidateRow
from memrise.integrations.postgres.session import session_scope


class PostgresCandidateRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

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
