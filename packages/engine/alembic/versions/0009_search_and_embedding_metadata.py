"""persist search_text and embedding provenance on memory versions

Revision ID: 0009_search_embedding_meta
Revises: 0008_graph_schema_packs
Create Date: 2026-07-03 16:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_search_embedding_meta"
down_revision: str | None = "0008_graph_schema_packs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("memory_versions", sa.Column("embedding_model", sa.String(128), nullable=True))
    op.add_column("memory_versions", sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
    op.add_column("memory_versions", sa.Column("embedding_text", sa.Text(), nullable=True))
    op.add_column("memory_versions", sa.Column("search_text", sa.Text(), nullable=True))

    # Generated columns cannot be altered in place: rebuild search_document to
    # include the extractor-provided search_text, then restore its GIN index.
    op.execute("DROP INDEX IF EXISTS ix_memory_versions_search_gin")
    op.drop_column("memory_versions", "search_document")
    op.execute(
        "ALTER TABLE memory_versions ADD COLUMN search_document tsvector "
        "GENERATED ALWAYS AS ("
        "to_tsvector('english', coalesce(content, '') || ' ' || coalesce(search_text, ''))"
        ") STORED"
    )
    op.execute(
        "CREATE INDEX ix_memory_versions_search_gin ON memory_versions USING gin (search_document)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memory_versions_search_gin")
    op.drop_column("memory_versions", "search_document")
    op.execute(
        "ALTER TABLE memory_versions ADD COLUMN search_document tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED"
    )
    op.execute(
        "CREATE INDEX ix_memory_versions_search_gin ON memory_versions USING gin (search_document)"
    )
    op.drop_column("memory_versions", "search_text")
    op.drop_column("memory_versions", "embedding_text")
    op.drop_column("memory_versions", "embedding_dimensions")
    op.drop_column("memory_versions", "embedding_model")
