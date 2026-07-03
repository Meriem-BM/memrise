from memrise.core.enums import (
    CandidateStageStatus,
    Criticality,
    EpisodeKind,
    JobStatus,
    JobType,
    MemoryStatus,
    MemoryType,
    RetrievalSourceType,
)
from memrise.core.models import (
    BackgroundJob,
    CanonicalMemory,
    Episode,
    MemoryCandidateStage,
    MemoryIdentity,
    MemoryVersion,
    RetrievalItem,
    RetrievalTrace,
)
from memrise.integrations.postgres.models import (
    EpisodeRow,
    JobRow,
    MemoryCandidateRow,
    MemoryRow,
    MemoryVersionRow,
    RetrievalItemRow,
    RetrievalTraceRow,
)


def episode_from_row(row: EpisodeRow) -> Episode:
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
        idempotency_key=row.idempotency_key,
    )


def canonical_from_rows(memory: MemoryRow, version: MemoryVersionRow) -> CanonicalMemory:
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


def retrieval_trace_from_row(row: RetrievalTraceRow) -> RetrievalTrace:
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


def retrieval_item_from_row(row: RetrievalItemRow) -> RetrievalItem:
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


def job_from_row(row: JobRow) -> BackgroundJob:
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


def candidate_stage_from_row(row: MemoryCandidateRow) -> MemoryCandidateStage:
    return MemoryCandidateStage(
        id=row.id,
        episode_id=row.episode_id,
        namespace_id=row.namespace_id,
        agent_id=row.agent_id,
        user_id=row.user_id,
        project_id=row.project_id,
        candidate_index=row.candidate_index,
        schema_version=row.schema_version,
        model_name=row.model_name,
        prompt_version=row.prompt_version,
        classification=dict(row.classification),
        candidate=dict(row.candidate),
        memory_type=row.memory_type,
        subject=row.subject,
        key=row.key,
        evidence_quote=row.evidence_quote,
        status=CandidateStageStatus(row.status),
        promotion_score=row.promotion_score,
        rejection_reason=row.rejection_reason,
        memory_version_id=row.memory_version_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
