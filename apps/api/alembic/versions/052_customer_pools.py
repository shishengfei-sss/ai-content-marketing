"""052 customer_pools + customers pool fields (v0.9 P1)

Revision ID: 052
Revises: 051
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "052"
down_revision: Union[str, None] = "051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_pools",
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
    op.create_index("ix_customer_pools_tenant_id", "customer_pools", ["tenant_id"])

    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pool_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.alter_column("owner_user_id", existing_type=sa.Uuid(), nullable=True)
        batch_op.create_foreign_key(
            "fk_customers_pool_id",
            "customer_pools",
            ["pool_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_customers_pool_id", ["pool_id"])


def downgrade() -> None:
    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.drop_index("ix_customers_pool_id")
        batch_op.drop_constraint("fk_customers_pool_id", type_="foreignkey")
        batch_op.drop_column("claimed_at")
        batch_op.drop_column("pool_id")
        batch_op.alter_column("owner_user_id", existing_type=sa.Uuid(), nullable=False)

    op.drop_index("ix_customer_pools_tenant_id", table_name="customer_pools")
    op.drop_table("customer_pools")
