from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from memrise.core.enums import MemoryStatus
from memrise.core.models import CanonicalMemory, Scope
from memrise.core.text import normalize_lookup
from memrise.core.time import utc_now
from memrise.integrations.postgres.schema.mappers import canonical_from_rows
from memrise.integrations.postgres.schema.models import MemoryRow, MemoryVersionRow
from memrise.learning.reconciliation import same_memory_value
from memrise.ports.providers import ExtractedMemoryCandidate


async def find_current_memory_in_session(
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
                or_(MemoryVersionRow.valid_until.is_(None), MemoryVersionRow.valid_until > now),
            )
            .order_by(MemoryVersionRow.version_number.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return canonical_from_rows(row[0], row[1])


async def lock_logical_memory_in_session(
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


async def find_matching_historical_memory_in_session(
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


async def find_latest_memory_in_session(
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
