"""add graph entities and claims

Revision ID: 0007_graph_claims
Revises: 0006_memory_storage_invariants
Create Date: 2026-07-03 12:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007_graph_claims"
down_revision: str | None = "0006_memory_storage_invariants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "graph_entities",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("namespace_id", sa.String(length=128), nullable=False),
        sa.Column("core_type", sa.String(length=64), nullable=False),
        sa.Column("domain_type", sa.String(length=128), nullable=True),
        sa.Column("canonical_name", sa.String(length=512), nullable=False),
        sa.Column("normalized_name", sa.String(length=512), nullable=False),
        sa.Column("aliases", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("stable_source_id", sa.String(length=256), nullable=True),
        sa.Column("user_id", sa.String(length=256), nullable=True),
        sa.Column("project_id", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "namespace_id",
            "core_type",
            "normalized_name",
            name="uq_graph_entities_identity",
        ),
    )
    op.create_index("ix_graph_entities_namespace_id", "graph_entities", ["namespace_id"])

    op.create_table(
        "graph_claims",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("namespace_id", sa.String(length=128), nullable=False),
        sa.Column("subject_entity_id", sa.String(length=80), nullable=False),
        sa.Column("predicate", sa.String(length=64), nullable=False),
        sa.Column("object_entity_id", sa.String(length=80), nullable=False),
        sa.Column("supporting_memory_version_id", sa.String(length=80), nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_claim_id", sa.String(length=80), nullable=True),
        sa.Column(
            "schema_version", sa.String(length=64), nullable=False, server_default="core@1.0"
        ),
        sa.Column("extractor_version", sa.String(length=64), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('active','superseded','contradicted','deprecated','expired','rejected')",
            name="ck_graph_claims_status",
        ),
        sa.ForeignKeyConstraint(
            ["subject_entity_id"],
            ["graph_entities.id"],
            name="fk_graph_claims_subject_entity_id",
        ),
        sa.ForeignKeyConstraint(
            ["object_entity_id"],
            ["graph_entities.id"],
            name="fk_graph_claims_object_entity_id",
        ),
        sa.ForeignKeyConstraint(
            ["supporting_memory_version_id"],
            ["memory_versions.id"],
            name="fk_graph_claims_supporting_memory_version_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_claim_id"],
            ["graph_claims.id"],
            name="fk_graph_claims_superseded_by_claim_id",
        ),
        sa.UniqueConstraint(
            "subject_entity_id",
            "predicate",
            "object_entity_id",
            "supporting_memory_version_id",
            name="uq_graph_claims_identity",
        ),
    )
    op.create_index("ix_graph_claims_namespace_id", "graph_claims", ["namespace_id"])
    op.create_index(
        "ix_graph_claims_supporting_memory_version_id",
        "graph_claims",
        ["supporting_memory_version_id"],
    )
    op.create_index("ix_graph_claims_status", "graph_claims", ["status"])


def downgrade() -> None:
    op.drop_index("ix_graph_claims_status", table_name="graph_claims")
    op.drop_index(
        "ix_graph_claims_supporting_memory_version_id",
        table_name="graph_claims",
    )
    op.drop_index("ix_graph_claims_namespace_id", table_name="graph_claims")
    op.drop_table("graph_claims")
    op.drop_index("ix_graph_entities_namespace_id", table_name="graph_entities")
    op.drop_table("graph_entities")
