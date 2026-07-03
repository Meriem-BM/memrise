"""add memory storage invariants

Revision ID: 0006_memory_storage_invariants
Revises: 0005_memory_candidate_staging
Create Date: 2026-07-03 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_memory_storage_invariants"
down_revision: str | None = "0005_memory_candidate_staging"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEDUPE_DUPLICATE_MEMORIES = sa.text(
    """
    WITH ranked AS (
        SELECT
            id,
            namespace_id,
            agent_id,
            user_id,
            project_id,
            normalized_subject,
            normalized_key,
            ROW_NUMBER() OVER (
                PARTITION BY
                    namespace_id,
                    agent_id,
                    user_id,
                    project_id,
                    normalized_subject,
                    normalized_key
                ORDER BY created_at ASC, id ASC
            ) AS rn
        FROM memories
    ),
    duplicate AS (
        SELECT r.id AS dupe_id, keeper.id AS keeper_id
        FROM ranked r
        JOIN ranked keeper
            ON keeper.namespace_id = r.namespace_id
            AND keeper.agent_id = r.agent_id
            AND keeper.user_id IS NOT DISTINCT FROM r.user_id
            AND keeper.project_id IS NOT DISTINCT FROM r.project_id
            AND keeper.normalized_subject = r.normalized_subject
            AND keeper.normalized_key = r.normalized_key
            AND keeper.rn = 1
        WHERE r.rn > 1
    ),
    keeper_versions AS (
        SELECT
            d.keeper_id,
            COALESCE(MAX(mv.version_number), 0) AS max_version
        FROM duplicate d
        LEFT JOIN memory_versions mv ON mv.memory_id = d.keeper_id
        GROUP BY d.keeper_id
    ),
    reassigned AS (
        SELECT
            mv.id AS version_id,
            d.keeper_id,
            kv.max_version + ROW_NUMBER() OVER (
                PARTITION BY mv.memory_id
                ORDER BY mv.version_number ASC
            ) AS new_version_number
        FROM memory_versions mv
        JOIN duplicate d ON d.dupe_id = mv.memory_id
        JOIN keeper_versions kv ON kv.keeper_id = d.keeper_id
    )
    UPDATE memory_versions AS mv
    SET
        memory_id = r.keeper_id,
        version_number = r.new_version_number
    FROM reassigned r
    WHERE mv.id = r.version_id
    """
)

_DELETE_DUPLICATE_MEMORIES = sa.text(
    """
    WITH ranked AS (
        SELECT
            id,
            ROW_NUMBER() OVER (
                PARTITION BY
                    namespace_id,
                    agent_id,
                    user_id,
                    project_id,
                    normalized_subject,
                    normalized_key
                ORDER BY created_at ASC, id ASC
            ) AS rn
        FROM memories
    )
    DELETE FROM memories
    WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
    """
)


def upgrade() -> None:
    op.execute(_DEDUPE_DUPLICATE_MEMORIES)
    op.execute(_DELETE_DUPLICATE_MEMORIES)
    op.create_index(
        "uq_memories_logical_identity",
        "memories",
        [
            "namespace_id",
            "agent_id",
            "user_id",
            "project_id",
            "normalized_subject",
            "normalized_key",
        ],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )
    op.create_check_constraint(
        "ck_memory_versions_version_number",
        "memory_versions",
        "version_number >= 1",
    )
    op.create_check_constraint(
        "ck_memory_versions_valid_window",
        "memory_versions",
        "valid_until is null or valid_until > valid_from",
    )
    op.create_index(
        "uq_memory_versions_version_number",
        "memory_versions",
        ["memory_id", "version_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_memory_versions_version_number", table_name="memory_versions")
    op.drop_constraint(
        "ck_memory_versions_valid_window",
        "memory_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_memory_versions_version_number",
        "memory_versions",
        type_="check",
    )
    op.drop_index("uq_memories_logical_identity", table_name="memories")
