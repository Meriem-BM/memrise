from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from memrise.core.enums import Criticality, MemoryStatus
from memrise.core.models import CanonicalMemory, Scope
from memrise.core.text import normalize_lookup, search_terms
from memrise.core.time import utc_now
from memrise.integrations.postgres.schema.mappers import canonical_from_rows
from memrise.integrations.postgres.schema.models import MemoryRow, MemoryVersionRow
from memrise.learning.apply import SEMANTIC_EQUIVALENCE_THRESHOLD
from memrise.learning.reconciliation import same_memory_value
from memrise.ports.providers import EmbeddingVector, ExtractedMemoryCandidate


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


async def find_semantic_duplicate_in_session(
    session: AsyncSession,
    *,
    scope: Scope,
    subject: str,
    exclude_key: str,
    embedding: EmbeddingVector,
) -> CanonicalMemory | None:
    """Find a live same-subject memory under a different key that says the same thing.

    Guards against LLM key instability creating duplicates ("package_manager" vs
    "preferred_package_manager"): a near-identical candidate is routed into
    reconciliation against the match instead of being added as a new memory.
    """
    if not embedding.values:
        return None
    now = utc_now()
    distance = MemoryVersionRow.embedding.cosine_distance(embedding.values)
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
                MemoryRow.normalized_key != normalize_lookup(exclude_key),
                MemoryVersionRow.status.in_(
                    [MemoryStatus.ACTIVE.value, MemoryStatus.CONTESTED.value]
                ),
                MemoryVersionRow.valid_from <= now,
                or_(MemoryVersionRow.valid_until.is_(None), MemoryVersionRow.valid_until > now),
                MemoryVersionRow.embedding.is_not(None),
                or_(
                    MemoryVersionRow.embedding_model.is_(None),
                    MemoryVersionRow.embedding_model == embedding.model,
                ),
                distance <= 1.0 - SEMANTIC_EQUIVALENCE_THRESHOLD,
            )
            .order_by(distance)
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return canonical_from_rows(row[0], row[1])


async def find_cross_subject_duplicate_in_session(
    session: AsyncSession,
    *,
    scope: Scope,
    subject: str,
    key: str,
    embedding: EmbeddingVector,
    threshold: float,
) -> CanonicalMemory | None:
    """Find the nearest live memory in scope under a *different* subject/key.

    Write-time duplicate prevention: reconciliation only compares a candidate to
    the one memory sharing its subject/key, so restatements phrased under a new
    subject (three wordings of one lockfile rule) would each be added. This
    scope-wide nearest-neighbor (HNSW index, one row) surfaces such a match so the
    apply pipeline reinforces the existing memory instead of creating a duplicate.
    The threshold is high, so distinct or contradictory facts are not matched.
    """
    if not embedding.values:
        return None
    now = utc_now()
    distance = MemoryVersionRow.embedding.cosine_distance(embedding.values)
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
                # Exclude the exact same logical identity (handled by find_current_memory).
                or_(
                    MemoryRow.normalized_subject != normalize_lookup(subject),
                    MemoryRow.normalized_key != normalize_lookup(key),
                ),
                MemoryVersionRow.status.in_(
                    [MemoryStatus.ACTIVE.value, MemoryStatus.CONTESTED.value]
                ),
                MemoryVersionRow.valid_from <= now,
                or_(MemoryVersionRow.valid_until.is_(None), MemoryVersionRow.valid_until > now),
                MemoryVersionRow.embedding.is_not(None),
                or_(
                    MemoryVersionRow.embedding_model.is_(None),
                    MemoryVersionRow.embedding_model == embedding.model,
                ),
                distance <= 1.0 - threshold,
            )
            .order_by(distance)
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return canonical_from_rows(row[0], row[1])


def _live_scope_filters(scope: Scope) -> list:
    """Filters shared by retrieval channels: live versions visible to the scope."""
    now = utc_now()
    return [
        MemoryRow.namespace_id == scope.namespace_id,
        MemoryRow.agent_id == scope.agent_id,
        or_(MemoryRow.user_id.is_(None), MemoryRow.user_id == scope.user_id),
        or_(MemoryRow.project_id.is_(None), MemoryRow.project_id == scope.project_id),
        MemoryVersionRow.status.in_([MemoryStatus.ACTIVE.value, MemoryStatus.CONTESTED.value]),
        MemoryVersionRow.valid_from <= now,
        or_(MemoryVersionRow.valid_until.is_(None), MemoryVersionRow.valid_until > now),
    ]


async def list_active_scopes_in_session(session: AsyncSession) -> list[Scope]:
    """Distinct scopes that currently hold live memories, for per-scope sweeps."""
    now = utc_now()
    rows = (
        await session.execute(
            select(
                MemoryRow.namespace_id,
                MemoryRow.agent_id,
                MemoryRow.user_id,
                MemoryRow.project_id,
            )
            .join(MemoryVersionRow, MemoryVersionRow.memory_id == MemoryRow.id)
            .where(
                MemoryVersionRow.status.in_(
                    [MemoryStatus.ACTIVE.value, MemoryStatus.CONTESTED.value]
                ),
                MemoryVersionRow.valid_from <= now,
                or_(MemoryVersionRow.valid_until.is_(None), MemoryVersionRow.valid_until > now),
            )
            .distinct()
        )
    ).all()
    return [
        Scope(namespace_id=namespace_id, agent_id=agent_id, user_id=user_id, project_id=project_id)
        for namespace_id, agent_id, user_id, project_id in rows
    ]


async def list_critical_memories_in_session(
    session: AsyncSession,
    *,
    scope: Scope,
    limit: int,
) -> list[CanonicalMemory]:
    rows = (
        await session.execute(
            select(MemoryRow, MemoryVersionRow)
            .join(MemoryVersionRow, MemoryVersionRow.memory_id == MemoryRow.id)
            .where(
                *_live_scope_filters(scope),
                MemoryVersionRow.criticality == Criticality.MUST_INCLUDE.value,
            )
            .order_by(
                (MemoryVersionRow.usefulness_score + MemoryVersionRow.confidence).desc(),
                MemoryVersionRow.updated_at.desc(),
            )
            .limit(limit)
        )
    ).all()
    return [canonical_from_rows(memory, version) for memory, version in rows]


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_structured_in_session(
    session: AsyncSession,
    *,
    scope: Scope,
    query: str,
    limit: int,
) -> list[CanonicalMemory]:
    """Bounded candidates whose normalized subject or key contains a query term.

    Exact structured scoring stays in the read service; this only bounds the pool.
    """
    terms = [term for term in search_terms(query) if term]
    if not terms:
        return []
    term_filters = []
    for term in terms:
        pattern = f"%{_escape_like(term)}%"
        term_filters.append(MemoryRow.normalized_subject.like(pattern, escape="\\"))
        term_filters.append(MemoryRow.normalized_key.like(pattern, escape="\\"))
    rows = (
        await session.execute(
            select(MemoryRow, MemoryVersionRow)
            .join(MemoryVersionRow, MemoryVersionRow.memory_id == MemoryRow.id)
            .where(*_live_scope_filters(scope), or_(*term_filters))
            .order_by(
                (MemoryVersionRow.usefulness_score + MemoryVersionRow.confidence).desc(),
                MemoryVersionRow.updated_at.desc(),
            )
            .limit(limit)
        )
    ).all()
    return [canonical_from_rows(memory, version) for memory, version in rows]


async def get_memories_by_version_ids_in_session(
    session: AsyncSession,
    *,
    scope: Scope,
    version_ids: list[str],
) -> list[CanonicalMemory]:
    """Scope-filtered hydration for graph hits: never returns versions outside the scope."""
    if not version_ids:
        return []
    rows = (
        await session.execute(
            select(MemoryRow, MemoryVersionRow)
            .join(MemoryVersionRow, MemoryVersionRow.memory_id == MemoryRow.id)
            .where(*_live_scope_filters(scope), MemoryVersionRow.id.in_(version_ids))
        )
    ).all()
    return [canonical_from_rows(memory, version) for memory, version in rows]


async def search_lexical_in_session(
    session: AsyncSession,
    *,
    scope: Scope,
    query: str,
    limit: int,
) -> list[tuple[CanonicalMemory, float]]:
    tsquery = func.websearch_to_tsquery("english", query)
    rank = func.ts_rank(MemoryVersionRow.search_document, tsquery)
    rows = (
        await session.execute(
            select(MemoryRow, MemoryVersionRow, rank.label("rank"))
            .join(MemoryVersionRow, MemoryVersionRow.memory_id == MemoryRow.id)
            .where(
                *_live_scope_filters(scope),
                MemoryVersionRow.search_document.op("@@")(tsquery),
            )
            .order_by(rank.desc())
            .limit(limit)
        )
    ).all()
    return [(canonical_from_rows(memory, version), float(score)) for memory, version, score in rows]


async def search_semantic_in_session(
    session: AsyncSession,
    *,
    scope: Scope,
    embedding: EmbeddingVector,
    limit: int,
) -> list[tuple[CanonicalMemory, float]]:
    if not embedding.values:
        return []
    distance = MemoryVersionRow.embedding.cosine_distance(embedding.values)
    rows = (
        await session.execute(
            select(MemoryRow, MemoryVersionRow, distance.label("distance"))
            .join(MemoryVersionRow, MemoryVersionRow.memory_id == MemoryRow.id)
            .where(
                *_live_scope_filters(scope),
                MemoryVersionRow.embedding.is_not(None),
                or_(
                    MemoryVersionRow.embedding_model.is_(None),
                    MemoryVersionRow.embedding_model == embedding.model,
                ),
            )
            .order_by(distance)
            .limit(limit)
        )
    ).all()
    return [
        (canonical_from_rows(memory, version), max(0.0, 1.0 - float(dist)))
        for memory, version, dist in rows
    ]
