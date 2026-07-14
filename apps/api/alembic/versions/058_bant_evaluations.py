"""058 bant_evaluations (v0.9 P1)

Revision ID: 058
Revises: 057
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "058"
down_revision: Union[str, None] = "057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bant_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("budget_score", sa.Integer(), nullable=False),
        sa.Column("authority_score", sa.Integer(), nullable=False),
        sa.Column("need_score", sa.Integer(), nullable=False),
        sa.Column("time_score", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Numeric(precision=3, scale=1), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bant_evaluations_tenant_id", "bant_evaluations", ["tenant_id"])
    op.create_index("ix_bant_evaluations_lead_id", "bant_evaluations", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_bant_evaluations_lead_id", table_name="bant_evaluations")
    op.drop_index("ix_bant_evaluations_tenant_id", table_name="bant_evaluations")
    op.drop_table("bant_evaluations")
