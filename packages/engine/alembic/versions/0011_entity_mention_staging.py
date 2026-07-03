"""stage ambiguous entity mentions instead of dropping their claims

Revision ID: 0011_entity_mention_staging
Revises: 0010_claim_usefulness
Create Date: 2026-07-03 18:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0011_entity_mention_staging"
down_revision: str | None = "0010_claim_usefulness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "graph_entity_mentions",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("namespace_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("normalized_name", sa.String(length=256), nullable=False),
        sa.Column("core_type", sa.String(length=128), nullable=False),
        sa.Column(
            "memory_version_id",
            sa.String(length=80),
            sa.ForeignKey("memory_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_entity_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ambiguous"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('ambiguous','resolved','dismissed')",
            name="ck_graph_entity_mentions_status",
        ),
    )
    op.create_index(
        "ix_graph_entity_mentions_namespace_id", "graph_entity_mentions", ["namespace_id"]
    )
    op.create_index(
        "ix_graph_entity_mentions_normalized_name", "graph_entity_mentions", ["normalized_name"]
    )
    op.create_index(
        "ix_graph_entity_mentions_memory_version_id",
        "graph_entity_mentions",
        ["memory_version_id"],
    )
    op.create_index("ix_graph_entity_mentions_status", "graph_entity_mentions", ["status"])


def downgrade() -> None:
    op.drop_table("graph_entity_mentions")
