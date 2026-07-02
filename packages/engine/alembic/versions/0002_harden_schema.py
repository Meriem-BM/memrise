"""harden v1 schema

Revision ID: 0002_harden_schema
Revises: 0001_initial
Create Date: 2026-07-02 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_harden_schema"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "namespaces",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("episodes", sa.Column("idempotency_key", sa.String(512), nullable=True))
    op.create_index(
        "uq_episodes_idempotency_key",
        "episodes",
        ["namespace_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.add_column(
        "memory_versions",
        sa.Column(
            "applicability",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "memory_versions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.drop_constraint("ck_jobs_type", "jobs", type_="check")
    op.create_check_constraint(
        "ck_jobs_type",
        "jobs",
        "type in ('extract_episode','consolidate_session','expire_memories',"
        "'process_feedback','project_graph','run_evaluation')",
    )
    op.create_table(
        "model_invocations",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("purpose", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("model", sa.String(256), nullable=False),
        sa.Column("prompt_version", sa.String(128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("error_code", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('succeeded','failed','retryable')",
            name="ck_model_invocations_status",
        ),
    )
    op.create_index("ix_model_invocations_purpose", "model_invocations", ["purpose", "created_at"])
    op.create_table(
        "graph_projection_jobs",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("namespace_id", sa.String(128), nullable=False),
        sa.Column(
            "memory_version_id",
            sa.String(80),
            sa.ForeignKey("memory_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('pending','completed','failed','skipped')",
            name="ck_graph_projection_jobs_status",
        ),
    )
    op.create_index(
        "ix_graph_projection_jobs_claim",
        "graph_projection_jobs",
        ["status", "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("namespace_id", sa.String(128), nullable=False),
        sa.Column("baseline", sa.String(128), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column(
            "metrics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('accepted','running','completed','failed')",
            name="ck_evaluation_runs_status",
        ),
    )
    op.create_index("ix_evaluation_runs_scope", "evaluation_runs", ["namespace_id", "created_at"])
    op.create_table(
        "evaluation_case_results",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(80),
            sa.ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("case_id", sa.String(128), nullable=False),
        sa.Column("baseline", sa.String(128), nullable=False),
        sa.Column(
            "metrics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_evaluation_case_results_run", "evaluation_case_results", ["run_id", "case_id"]
    )


def downgrade() -> None:
    op.drop_table("evaluation_case_results")
    op.drop_table("evaluation_runs")
    op.drop_table("graph_projection_jobs")
    op.drop_table("model_invocations")
    op.drop_constraint("ck_jobs_type", "jobs", type_="check")
    op.create_check_constraint(
        "ck_jobs_type",
        "jobs",
        "type in ('extract_episode','consolidate_session','expire_memories','process_feedback')",
    )
    op.drop_column("memory_versions", "updated_at")
    op.drop_column("memory_versions", "applicability")
    op.drop_index("uq_episodes_idempotency_key", table_name="episodes")
    op.drop_column("episodes", "idempotency_key")
    op.drop_table("namespaces")
