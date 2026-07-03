"""add memory candidate staging

Revision ID: 0005_memory_candidate_staging
Revises: 0004_public_schema
Create Date: 2026-07-03 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_memory_candidate_staging"
down_revision: str | None = "0004_public_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_candidates",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column(
            "episode_id",
            sa.String(80),
            sa.ForeignKey("episodes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("namespace_id", sa.String(128), nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.String(256), nullable=True),
        sa.Column("project_id", sa.String(256), nullable=True),
        sa.Column("candidate_index", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(128), nullable=False),
        sa.Column("model_name", sa.String(256), nullable=False),
        sa.Column("prompt_version", sa.String(128), nullable=False),
        sa.Column(
            "classification",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "candidate",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("memory_type", sa.String(64), nullable=True),
        sa.Column("subject", sa.String(512), nullable=True),
        sa.Column("key", sa.String(512), nullable=True),
        sa.Column("evidence_quote", sa.Text(), nullable=True),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("promotion_score", sa.Float(), nullable=False),
        sa.Column("rejection_reason", sa.String(256), nullable=True),
        sa.Column(
            "memory_version_id",
            sa.String(80),
            sa.ForeignKey("memory_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('staged','promoted','rejected','failed')",
            name="ck_memory_candidates_status",
        ),
        sa.CheckConstraint(
            "promotion_score >= 0 and promotion_score <= 1",
            name="ck_memory_candidates_promotion_score",
        ),
        sa.UniqueConstraint(
            "episode_id",
            "candidate_index",
            name="uq_memory_candidates_episode_index",
        ),
    )
    op.create_index(
        "ix_memory_candidates_episode",
        "memory_candidates",
        ["episode_id"],
    )
    op.create_index(
        "ix_memory_candidates_scope_status",
        "memory_candidates",
        ["namespace_id", "status", "created_at"],
    )
    op.create_index(
        "ix_memory_candidates_memory_version",
        "memory_candidates",
        ["memory_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_memory_candidates_memory_version", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_scope_status", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_episode", table_name="memory_candidates")
    op.drop_table("memory_candidates")
