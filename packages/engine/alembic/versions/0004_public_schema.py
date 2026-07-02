"""relocate application tables to public schema

Revision ID: 0004_public_schema
Revises: 0003_remove_evaluations
Create Date: 2026-07-02 00:00:00.000000+00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_public_schema"
down_revision: str | None = "0003_remove_evaluations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APPLICATION_TABLES = (
    "episodes",
    "memories",
    "memory_versions",
    "memory_sources",
    "retrieval_traces",
    "retrieval_items",
    "retrieval_feedback",
    "jobs",
    "namespaces",
    "model_invocations",
    "graph_projection_jobs",
)


def _relocate_tables(*, source_schema: str, target_schema: str, tables: tuple[str, ...]) -> None:
    for table in tables:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = '{source_schema}' AND table_name = '{table}'
                ) THEN
                    ALTER TABLE {source_schema}.{table} SET SCHEMA {target_schema};
                END IF;
            END
            $$;
            """
        )


def upgrade() -> None:
    _relocate_tables(
        source_schema="ag_catalog",
        target_schema="public",
        tables=_APPLICATION_TABLES,
    )
    op.execute('SET search_path = "$user", public')


def downgrade() -> None:
    op.execute('SET search_path = ag_catalog, "$user", public')
    _relocate_tables(
        source_schema="public",
        target_schema="ag_catalog",
        tables=tuple(reversed(_APPLICATION_TABLES)),
    )
