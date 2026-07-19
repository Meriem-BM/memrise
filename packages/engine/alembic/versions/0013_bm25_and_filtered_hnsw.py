"""add BM25 lexical search and align HNSW with live retrieval

Revision ID: 0013_bm25_hnsw
Revises: 0012_dedupe_job_type
Create Date: 2026-07-19 12:00:00.000000+00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013_bm25_hnsw"
down_revision: str | None = "0012_dedupe_job_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEXICAL_EXPRESSION = "(coalesce(content, '') || ' ' || coalesce(search_text, ''))"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_textsearch")
    op.execute(
        "CREATE INDEX ix_memory_versions_lexical_bm25 "
        f"ON memory_versions USING bm25 ({_LEXICAL_EXPRESSION}) "
        "WITH (text_config='english') "
        "WHERE status IN ('active', 'contested')"
    )
    op.execute("DROP INDEX IF EXISTS ix_memory_versions_embedding_hnsw")
    op.execute(
        "CREATE INDEX ix_memory_versions_embedding_hnsw "
        "ON memory_versions USING hnsw (embedding vector_cosine_ops) "
        "WHERE status IN ('active', 'contested') AND embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memory_versions_lexical_bm25")
    op.execute("DROP INDEX IF EXISTS ix_memory_versions_embedding_hnsw")
    op.execute(
        "CREATE INDEX ix_memory_versions_embedding_hnsw "
        "ON memory_versions USING hnsw (embedding vector_cosine_ops) "
        "WHERE status = 'active' AND embedding IS NOT NULL"
    )
