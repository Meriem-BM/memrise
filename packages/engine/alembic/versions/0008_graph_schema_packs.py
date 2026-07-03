"""add graph schema packs and candidates

Revision ID: 0008_graph_schema_packs
Revises: 0007_graph_claims
Create Date: 2026-07-03 14:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0008_graph_schema_packs"
down_revision: str | None = "0007_graph_claims"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "graph_schema_packs",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("namespace_id", sa.String(length=128), nullable=True),
        sa.Column("project_id", sa.String(length=256), nullable=True),
        sa.Column("domain", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("definition", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('proposed','active','deprecated')",
            name="ck_graph_schema_packs_status",
        ),
        sa.UniqueConstraint(
            "namespace_id",
            "project_id",
            "domain",
            "version",
            name="uq_graph_schema_packs_scope",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index("ix_graph_schema_packs_namespace_id", "graph_schema_packs", ["namespace_id"])
    op.create_index("ix_graph_schema_packs_status", "graph_schema_packs", ["status"])

    op.create_table(
        "graph_schema_candidates",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("namespace_id", sa.String(length=128), nullable=False),
        sa.Column("domain", sa.String(length=128), nullable=False),
        sa.Column("candidate_type", sa.String(length=128), nullable=False),
        sa.Column("candidate_kind", sa.String(length=32), nullable=False),
        sa.Column("fallback_type", sa.String(length=128), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("example_context", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="proposed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "candidate_kind in ('node_type','relation_type')",
            name="ck_graph_schema_candidates_kind",
        ),
        sa.CheckConstraint(
            "status in ('proposed','accepted','rejected')",
            name="ck_graph_schema_candidates_status",
        ),
        sa.UniqueConstraint(
            "namespace_id",
            "domain",
            "candidate_type",
            "candidate_kind",
            name="uq_graph_schema_candidates_identity",
        ),
    )
    op.create_index(
        "ix_graph_schema_candidates_namespace_id",
        "graph_schema_candidates",
        ["namespace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_graph_schema_candidates_namespace_id", table_name="graph_schema_candidates")
    op.drop_table("graph_schema_candidates")
    op.drop_index("ix_graph_schema_packs_status", table_name="graph_schema_packs")
    op.drop_index("ix_graph_schema_packs_namespace_id", table_name="graph_schema_packs")
    op.drop_table("graph_schema_packs")
