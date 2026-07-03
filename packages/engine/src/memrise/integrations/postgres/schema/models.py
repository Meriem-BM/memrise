from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class NamespaceRow(Base):
    __tablename__ = "namespaces"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(256))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class EpisodeRow(Base):
    __tablename__ = "episodes"
    __table_args__ = (
        CheckConstraint(
            "kind in ('user_message','agent_message','tool_call','tool_result','user_feedback',"
            "'task_result','environment_observation')",
            name="ck_episodes_kind",
        ),
        Index(
            "uq_episodes_idempotency_key",
            "namespace_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    namespace_id: Mapped[str] = mapped_column(String(128), index=True)
    agent_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    session_id: Mapped[str] = mapped_column(String(256), index=True)
    project_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MemoryRow(Base):
    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint(
            "type in ('preference','fact','decision','constraint','goal','lesson')",
            name="ck_memories_type",
        ),
        Index(
            "uq_memories_logical_identity",
            "namespace_id",
            "agent_id",
            "user_id",
            "project_id",
            "normalized_subject",
            "normalized_key",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    namespace_id: Mapped[str] = mapped_column(String(128), index=True)
    agent_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    type: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(512))
    key: Mapped[str] = mapped_column(String(512))
    normalized_subject: Mapped[str] = mapped_column(String(512))
    normalized_key: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MemoryVersionRow(Base):
    __tablename__ = "memory_versions"
    __table_args__ = (
        CheckConstraint(
            "status in ('candidate','active','superseded','expired','contested','deleted')",
            name="ck_memory_versions_status",
        ),
        CheckConstraint(
            "criticality in ('normal','high_priority','must_include')",
            name="ck_memory_versions_criticality",
        ),
        CheckConstraint(
            "confidence >= 0 and confidence <= 1", name="ck_memory_versions_confidence"
        ),
        CheckConstraint(
            "importance >= 0 and importance <= 1", name="ck_memory_versions_importance"
        ),
        CheckConstraint(
            "usefulness_score >= 0 and usefulness_score <= 1",
            name="ck_memory_versions_usefulness",
        ),
        CheckConstraint("version_number >= 1", name="ck_memory_versions_version_number"),
        CheckConstraint(
            "valid_until is null or valid_until > valid_from",
            name="ck_memory_versions_valid_window",
        ),
        Index(
            "uq_memory_versions_version_number",
            "memory_id",
            "version_number",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("memories.id", ondelete="RESTRICT"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    structured_value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    applicability: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float]
    importance: Mapped[float]
    criticality: Mapped[str] = mapped_column(String(64), index=True)
    usefulness_score: Mapped[float]
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    superseded_by_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_document: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(content, '') || ' ' || coalesce(search_text, ''))",
            persisted=True,
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MemorySourceRow(Base):
    __tablename__ = "memory_sources"

    memory_version_id: Mapped[str] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    episode_id: Mapped[str] = mapped_column(
        ForeignKey("episodes.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    relation: Mapped[str] = mapped_column(String(64), primary_key=True)


class MemoryCandidateRow(Base):
    __tablename__ = "memory_candidates"
    __table_args__ = (
        CheckConstraint(
            "status in ('staged','promoted','rejected','failed')",
            name="ck_memory_candidates_status",
        ),
        CheckConstraint(
            "promotion_score >= 0 and promotion_score <= 1",
            name="ck_memory_candidates_promotion_score",
        ),
        UniqueConstraint(
            "episode_id", "candidate_index", name="uq_memory_candidates_episode_index"
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    episode_id: Mapped[str] = mapped_column(
        ForeignKey("episodes.id", ondelete="RESTRICT"), index=True
    )
    namespace_id: Mapped[str] = mapped_column(String(128), index=True)
    agent_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    candidate_index: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(128))
    model_name: Mapped[str] = mapped_column(String(256))
    prompt_version: Mapped[str] = mapped_column(String(128))
    classification: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    candidate: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    memory_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    evidence_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    promotion_score: Mapped[float] = mapped_column(Float)
    rejection_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    memory_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RetrievalTraceRow(Base):
    __tablename__ = "retrieval_traces"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    namespace_id: Mapped[str] = mapped_column(String(128), index=True)
    agent_id: Mapped[str] = mapped_column(String(128), index=True)
    query: Mapped[str] = mapped_column(Text)
    task_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    token_budget: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RetrievalItemRow(Base):
    __tablename__ = "retrieval_items"

    retrieval_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_traces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    original_rank: Mapped[int] = mapped_column(Integer, primary_key=True)
    memory_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    graph_edge_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    final_rank: Mapped[int] = mapped_column(Integer)
    lexical_score: Mapped[float | None] = mapped_column(nullable=True)
    semantic_score: Mapped[float | None] = mapped_column(nullable=True)
    graph_score: Mapped[float | None] = mapped_column(nullable=True)
    usefulness_score: Mapped[float]
    selected_for_context: Mapped[bool]
    token_count: Mapped[int]


class RetrievalFeedbackRow(Base):
    __tablename__ = "retrieval_feedback"
    __table_args__ = (
        CheckConstraint("outcome in ('helpful','unused','harmful')", name="ck_feedback_outcome"),
        CheckConstraint(
            "source in ('user','developer','tool','evaluator','agent')",
            name="ck_feedback_source",
        ),
        CheckConstraint("confidence >= 0 and confidence <= 1", name="ck_feedback_confidence"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    retrieval_id: Mapped[str] = mapped_column(ForeignKey("retrieval_traces.id", ondelete="CASCADE"))
    memory_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    graph_edge_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    outcome: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float]
    task_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class JobRow(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "type in ('extract_episode','consolidate_session',"
            "'expire_memories','process_feedback','project_graph')",
            name="ck_jobs_type",
        ),
        CheckConstraint(
            "status in ('pending','running','completed','failed','retryable')",
            name="ck_jobs_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_jobs_attempts"),
        CheckConstraint("max_attempts >= 1", name="ck_jobs_max_attempts"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(64), index=True)
    attempts: Mapped[int] = mapped_column(Integer)
    max_attempts: Mapped[int] = mapped_column(Integer)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(512), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ModelInvocationRow(Base):
    __tablename__ = "model_invocations"
    __table_args__ = (
        CheckConstraint(
            "status in ('succeeded','failed','retryable')", name="ck_model_invocations_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(128), index=True)
    provider: Mapped[str] = mapped_column(String(128))
    model: Mapped[str] = mapped_column(String(256))
    prompt_version: Mapped[str] = mapped_column(String(128))
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(64), index=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GraphEntityRow(Base):
    __tablename__ = "graph_entities"
    __table_args__ = (
        UniqueConstraint(
            "namespace_id",
            "core_type",
            "normalized_name",
            name="uq_graph_entities_identity",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    namespace_id: Mapped[str] = mapped_column(String(128), index=True)
    core_type: Mapped[str] = mapped_column(String(64))
    domain_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    canonical_name: Mapped[str] = mapped_column(String(512))
    normalized_name: Mapped[str] = mapped_column(String(512))
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    stable_source_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GraphClaimRow(Base):
    __tablename__ = "graph_claims"
    __table_args__ = (
        CheckConstraint(
            "status in ('active','superseded','contradicted','deprecated','expired','rejected')",
            name="ck_graph_claims_status",
        ),
        UniqueConstraint(
            "subject_entity_id",
            "predicate",
            "object_entity_id",
            "supporting_memory_version_id",
            name="uq_graph_claims_identity",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    namespace_id: Mapped[str] = mapped_column(String(128), index=True)
    subject_entity_id: Mapped[str] = mapped_column(
        ForeignKey("graph_entities.id"),
    )
    predicate: Mapped[str] = mapped_column(String(64))
    object_entity_id: Mapped[str] = mapped_column(
        ForeignKey("graph_entities.id"),
    )
    supporting_memory_version_id: Mapped[str] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="CASCADE"),
        index=True,
    )
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_claim_id: Mapped[str | None] = mapped_column(
        ForeignKey("graph_claims.id"),
        nullable=True,
    )
    schema_version: Mapped[str] = mapped_column(String(64), default="core@1.0")
    extractor_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GraphSchemaPackRow(Base):
    __tablename__ = "graph_schema_packs"
    __table_args__ = (
        CheckConstraint(
            "status in ('proposed','active','deprecated')",
            name="ck_graph_schema_packs_status",
        ),
        UniqueConstraint(
            "namespace_id",
            "project_id",
            "domain",
            "version",
            name="uq_graph_schema_packs_scope",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    namespace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    domain: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(64), index=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GraphSchemaCandidateRow(Base):
    __tablename__ = "graph_schema_candidates"
    __table_args__ = (
        CheckConstraint(
            "candidate_kind in ('node_type','relation_type')",
            name="ck_graph_schema_candidates_kind",
        ),
        CheckConstraint(
            "status in ('proposed','accepted','rejected')",
            name="ck_graph_schema_candidates_status",
        ),
        UniqueConstraint(
            "namespace_id",
            "domain",
            "candidate_type",
            "candidate_kind",
            name="uq_graph_schema_candidates_identity",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    namespace_id: Mapped[str] = mapped_column(String(128), index=True)
    domain: Mapped[str] = mapped_column(String(128))
    candidate_type: Mapped[str] = mapped_column(String(128))
    candidate_kind: Mapped[str] = mapped_column(String(32))
    fallback_type: Mapped[str] = mapped_column(String(128))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    example_context: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GraphProjectionJobRow(Base):
    __tablename__ = "graph_projection_jobs"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending','completed','failed','skipped')",
            name="ck_graph_projection_jobs_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    namespace_id: Mapped[str] = mapped_column(String(128), index=True)
    memory_version_id: Mapped[str] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(64), index=True)
    attempts: Mapped[int] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
