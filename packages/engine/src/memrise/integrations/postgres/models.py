from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EpisodeRow(Base):
    __tablename__ = "episodes"
    __table_args__ = (
        CheckConstraint(
            "kind in ('user_message','agent_message','tool_call','tool_result','user_feedback',"
            "'task_result','environment_observation')",
            name="ck_episodes_kind",
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MemoryRow(Base):
    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint(
            "type in ('preference','fact','decision','constraint','goal','lesson')",
            name="ck_memories_type",
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
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("memories.id", ondelete="RESTRICT"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    structured_value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
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
    search_document: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(content, ''))", persisted=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


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


class GraphNodeRow(Base):
    __tablename__ = "graph_nodes"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    namespace_id: Mapped[str] = mapped_column(String(128), index=True)
    project_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    node_type: Mapped[str] = mapped_column(String(128))
    canonical_name: Mapped[str] = mapped_column(String(512))
    normalized_name: Mapped[str] = mapped_column(String(512), index=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class GraphEdgeRow(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        CheckConstraint(
            "status in ('active','superseded','expired','contested','deleted')",
            name="ck_graph_edges_status",
        ),
        CheckConstraint("confidence >= 0 and confidence <= 1", name="ck_graph_edges_confidence"),
        CheckConstraint(
            "usefulness_score >= 0 and usefulness_score <= 1",
            name="ck_graph_edges_usefulness",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_node_id: Mapped[str] = mapped_column(ForeignKey("graph_nodes.id", ondelete="CASCADE"))
    target_node_id: Mapped[str] = mapped_column(ForeignKey("graph_nodes.id", ondelete="CASCADE"))
    relation: Mapped[str] = mapped_column(String(128))
    source_memory_version_id: Mapped[str] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="RESTRICT"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float]
    usefulness_score: Mapped[float]
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
    graph_edge_id: Mapped[str | None] = mapped_column(
        ForeignKey("graph_edges.id", ondelete="SET NULL"),
        nullable=True,
    )
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
    graph_edge_id: Mapped[str | None] = mapped_column(
        ForeignKey("graph_edges.id", ondelete="SET NULL"),
        nullable=True,
    )
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
            "'expire_memories','process_feedback')",
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
