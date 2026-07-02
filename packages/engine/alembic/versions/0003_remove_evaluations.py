"""remove evaluations

Revision ID: 0003_remove_evaluations
Revises: 0002_harden_schema
Create Date: 2026-07-02 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_remove_evaluations"
down_revision: str | None = "0002_harden_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("evaluation_case_results")
    op.drop_table("evaluation_runs")
    op.drop_constraint("ck_jobs_type", "jobs", type_="check")
    op.create_check_constraint(
        "ck_jobs_type",
        "jobs",
        "type in ('extract_episode','consolidate_session','expire_memories',"
        "'process_feedback','project_graph')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_jobs_type", "jobs", type_="check")
    op.create_check_constraint(
        "ck_jobs_type",
        "jobs",
        "type in ('extract_episode','consolidate_session','expire_memories',"
        "'process_feedback','project_graph','run_evaluation')",
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
        "ix_evaluation_case_results_run",
        "evaluation_case_results",
        ["run_id", "case_id"],
    )
