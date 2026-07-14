"""051 lead_pools + leads pool fields (v0.9 P1)

Revision ID: 051
Revises: 050
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "051"
down_revision: Union[str, None] = "050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_pools",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("territory_id", sa.Uuid(), nullable=True),
        sa.Column("industry_filter", sa.String(length=100), nullable=True),
        sa.Column("auto_reclaim_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_pools_tenant_id", "lead_pools", ["tenant_id"])

    with op.batch_alter_table("leads", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pool_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.alter_column("owner_user_id", existing_type=sa.Uuid(), nullable=True)
        batch_op.create_foreign_key(
            "fk_leads_pool_id",
            "lead_pools",
            ["pool_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_leads_pool_id", ["pool_id"])


def downgrade() -> None:
    with op.batch_alter_table("leads", schema=None) as batch_op:
        batch_op.drop_index("ix_leads_pool_id")
        batch_op.drop_constraint("fk_leads_pool_id", type_="foreignkey")
        batch_op.drop_column("claimed_at")
        batch_op.drop_column("pool_id")
        batch_op.alter_column("owner_user_id", existing_type=sa.Uuid(), nullable=False)

    op.drop_index("ix_lead_pools_tenant_id", table_name="lead_pools")
    op.drop_table("lead_pools")
