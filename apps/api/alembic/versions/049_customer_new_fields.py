"""049 customer new fields for v0.9 P0

Revision ID: 049
Revises: 048
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "049"
down_revision: Union[str, None] = "048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("type", sa.String(length=20), nullable=True, server_default="客户")
        )
        batch_op.add_column(sa.Column("parent_customer_id", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "total_revenue",
                sa.Numeric(precision=14, scale=2),
                nullable=True,
                server_default="0",
            )
        )
        batch_op.add_column(sa.Column("last_deal_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("source", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("converted_lead_score", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_customers_parent_customer_id",
            "customers",
            ["parent_customer_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_customers_parent_customer_id", ["parent_customer_id"])
        batch_op.create_index("ix_customers_type", ["type"])
        batch_op.create_index("ix_customers_source", ["source"])


def downgrade() -> None:
    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.drop_index("ix_customers_source")
        batch_op.drop_index("ix_customers_type")
        batch_op.drop_index("ix_customers_parent_customer_id")
        batch_op.drop_constraint("fk_customers_parent_customer_id", type_="foreignkey")
        batch_op.drop_column("converted_lead_score")
        batch_op.drop_column("source")
        batch_op.drop_column("tags")
        batch_op.drop_column("last_deal_date")
        batch_op.drop_column("total_revenue")
        batch_op.drop_column("parent_customer_id")
        batch_op.drop_column("type")
        batch_op.drop_column("description")
