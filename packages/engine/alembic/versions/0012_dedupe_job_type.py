"""allow dedupe_memories (and rebuild_graph) job types

Revision ID: 0012_dedupe_job_type
Revises: 0011_entity_mention_staging
Create Date: 2026-07-06 10:00:00.000000+00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012_dedupe_job_type"
down_revision: str | None = "0011_entity_mention_staging"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The check constraint had drifted from the JobType enum: it still allowed the
# removed process_feedback and never allowed rebuild_graph or the new
# dedupe_memories sweep. Realign it with the enum.
_NEW = (
    "type in ('extract_episode','consolidate_session','expire_memories',"
    "'dedupe_memories','project_graph','rebuild_graph')"
)
_OLD = (
    "type in ('extract_episode','consolidate_session','expire_memories',"
    "'process_feedback','project_graph')"
)


def upgrade() -> None:
    op.drop_constraint("ck_jobs_type", "jobs", type_="check")
    op.create_check_constraint("ck_jobs_type", "jobs", _NEW)


def downgrade() -> None:
    op.drop_constraint("ck_jobs_type", "jobs", type_="check")
    op.create_check_constraint("ck_jobs_type", "jobs", _OLD)
