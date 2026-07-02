"""initial temporal hybrid memory schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-01 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS age")
    op.execute("LOAD 'age'")
    op.execute('SET search_path = ag_catalog, "$user", public')
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'memrise_graph'
            ) THEN
                PERFORM create_graph('memrise_graph');
            END IF;
        END
        $$;
        """
    )

    op.create_table(
        "episodes",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("namespace_id", sa.String(128), nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.String(256), nullable=True),
        sa.Column("session_id", sa.String(256), nullable=False),
        sa.Column("project_id", sa.String(256), nullable=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind in ('user_message','agent_message','tool_call','tool_result','user_feedback',"
            "'task_result','environment_observation')",
            name="ck_episodes_kind",
        ),
    )
    op.create_index(
        "ix_episodes_namespace_scope", "episodes", ["namespace_id", "agent_id", "session_id"]
    )
    op.create_index(
        "ix_episodes_project_created", "episodes", ["namespace_id", "project_id", "created_at"]
    )

    op.create_table(
        "memories",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("namespace_id", sa.String(128), nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.String(256), nullable=True),
        sa.Column("project_id", sa.String(256), nullable=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("key", sa.String(512), nullable=False),
        sa.Column("normalized_subject", sa.String(512), nullable=False),
        sa.Column("normalized_key", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type in ('preference','fact','decision','constraint','goal','lesson')",
            name="ck_memories_type",
        ),
    )
    op.create_index(
        "ix_memories_lookup",
        "memories",
        [
            "namespace_id",
            "agent_id",
            "project_id",
            "user_id",
            "normalized_subject",
            "normalized_key",
        ],
    )
    op.create_index("ix_memories_namespace_type", "memories", ["namespace_id", "type"])

    op.create_table(
        "memory_versions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column(
            "memory_id",
            sa.String(80),
            sa.ForeignKey("memories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "structured_value",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("criticality", sa.String(64), nullable=False),
        sa.Column("usefulness_score", sa.Float(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "supersedes_version_id",
            sa.String(80),
            sa.ForeignKey("memory_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "superseded_by_version_id",
            sa.String(80),
            sa.ForeignKey("memory_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "search_document",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', coalesce(content, ''))", persisted=True),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('candidate','active','superseded','expired','contested','deleted')",
            name="ck_memory_versions_status",
        ),
        sa.CheckConstraint(
            "criticality in ('normal','high_priority','must_include')",
            name="ck_memory_versions_criticality",
        ),
        sa.CheckConstraint(
            "confidence >= 0 and confidence <= 1", name="ck_memory_versions_confidence"
        ),
        sa.CheckConstraint(
            "importance >= 0 and importance <= 1", name="ck_memory_versions_importance"
        ),
        sa.CheckConstraint(
            "usefulness_score >= 0 and usefulness_score <= 1",
            name="ck_memory_versions_usefulness",
        ),
    )
    op.create_index("ix_memory_versions_memory", "memory_versions", ["memory_id", "version_number"])
    op.create_index(
        "ix_memory_versions_lifecycle",
        "memory_versions",
        ["status", "criticality", "valid_from", "valid_until"],
    )
    op.create_index(
        "uq_memory_versions_one_active",
        "memory_versions",
        ["memory_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.execute(
        "CREATE INDEX ix_memory_versions_search_gin "
        "ON memory_versions USING gin (search_document) "
        "WHERE status = 'active'"
    )
    op.execute(
        "CREATE INDEX ix_memory_versions_embedding_hnsw "
        "ON memory_versions USING hnsw (embedding vector_cosine_ops) "
        "WHERE status = 'active' AND embedding IS NOT NULL"
    )

    op.create_table(
        "memory_sources",
        sa.Column(
            "memory_version_id",
            sa.String(80),
            sa.ForeignKey("memory_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "episode_id",
            sa.String(80),
            sa.ForeignKey("episodes.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("relation", sa.String(64), primary_key=True),
    )

    op.create_table(
        "retrieval_traces",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("namespace_id", sa.String(128), nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(128), nullable=True),
        sa.Column("project_id", sa.String(256), nullable=True),
        sa.Column("token_budget", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_retrieval_traces_scope", "retrieval_traces", ["namespace_id", "agent_id", "created_at"]
    )

    op.create_table(
        "retrieval_items",
        sa.Column(
            "retrieval_id",
            sa.String(80),
            sa.ForeignKey("retrieval_traces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("source_type", sa.String(64), primary_key=True),
        sa.Column("original_rank", sa.Integer(), primary_key=True),
        sa.Column(
            "memory_version_id",
            sa.String(80),
            sa.ForeignKey("memory_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("graph_edge_id", sa.String(80), nullable=True),
        sa.Column("final_rank", sa.Integer(), nullable=False),
        sa.Column("lexical_score", sa.Float(), nullable=True),
        sa.Column("semantic_score", sa.Float(), nullable=True),
        sa.Column("graph_score", sa.Float(), nullable=True),
        sa.Column("usefulness_score", sa.Float(), nullable=False),
        sa.Column("selected_for_context", sa.Boolean(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_retrieval_items_memory", "retrieval_items", ["memory_version_id"])

    op.create_table(
        "retrieval_feedback",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column(
            "retrieval_id",
            sa.String(80),
            sa.ForeignKey("retrieval_traces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "memory_version_id",
            sa.String(80),
            sa.ForeignKey("memory_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("graph_edge_id", sa.String(80), nullable=True),
        sa.Column("outcome", sa.String(64), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("task_type", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("outcome in ('helpful','unused','harmful')", name="ck_feedback_outcome"),
        sa.CheckConstraint(
            "source in ('user','developer','tool','evaluator','agent')",
            name="ck_feedback_source",
        ),
        sa.CheckConstraint("confidence >= 0 and confidence <= 1", name="ck_feedback_confidence"),
    )
    op.create_index("ix_feedback_memory", "retrieval_feedback", ["memory_version_id", "created_at"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(256), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.String(512), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type in ('extract_episode','consolidate_session',"
            "'expire_memories','process_feedback','project_graph')",
            name="ck_jobs_type",
        ),
        sa.CheckConstraint(
            "status in ('pending','running','completed','failed','retryable')",
            name="ck_jobs_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_jobs_attempts"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_jobs_max_attempts"),
    )
    op.create_index(
        "ix_jobs_claim",
        "jobs",
        ["status", "run_at", "created_at"],
        postgresql_where=sa.text("status in ('pending','retryable')"),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("retrieval_feedback")
    op.drop_table("retrieval_items")
    op.drop_table("retrieval_traces")
    op.drop_table("memory_sources")
    op.drop_table("memory_versions")
    op.drop_table("memories")
    op.drop_table("episodes")
    op.execute("DROP EXTENSION IF EXISTS age")
    op.execute("DROP EXTENSION IF EXISTS vector")
