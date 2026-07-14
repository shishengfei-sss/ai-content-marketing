"""046 deal_close_analyses table (v0.8 deal P2-03)

Revision ID: 046
Revises: 045
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deal_close_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("close_type", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("competitor", sa.String(length=200), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("improvement", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deal_close_analyses_tenant_id", "deal_close_analyses", ["tenant_id"])
    op.create_index("ix_deal_close_analyses_deal_id", "deal_close_analyses", ["deal_id"])


def downgrade() -> None:
    op.drop_index("ix_deal_close_analyses_deal_id", table_name="deal_close_analyses")
    op.drop_index("ix_deal_close_analyses_tenant_id", table_name="deal_close_analyses")
    op.drop_table("deal_close_analyses")
