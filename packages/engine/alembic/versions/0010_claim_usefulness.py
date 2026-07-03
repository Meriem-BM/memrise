"""track usefulness on graph claims so rebuilds preserve learning

Revision ID: 0010_claim_usefulness
Revises: 0009_search_embedding_meta
Create Date: 2026-07-03 17:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_claim_usefulness"
down_revision: str | None = "0009_search_embedding_meta"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "graph_claims",
        sa.Column("usefulness_score", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.create_check_constraint(
        "ck_graph_claims_usefulness",
        "graph_claims",
        "usefulness_score >= 0 and usefulness_score <= 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_graph_claims_usefulness", "graph_claims", type_="check")
    op.drop_column("graph_claims", "usefulness_score")
