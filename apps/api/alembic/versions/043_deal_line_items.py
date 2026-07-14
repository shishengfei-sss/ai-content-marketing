"""043 deal_line_items table (v0.8 deal P1-03)

Revision ID: 043
Revises: 042
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "043"
down_revision: Union[str, None] = "042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deal_line_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("product_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deal_line_items_tenant_id", "deal_line_items", ["tenant_id"])
    op.create_index("ix_deal_line_items_deal_id", "deal_line_items", ["deal_id"])


def downgrade() -> None:
    op.drop_index("ix_deal_line_items_deal_id", table_name="deal_line_items")
    op.drop_index("ix_deal_line_items_tenant_id", table_name="deal_line_items")
    op.drop_table("deal_line_items")
