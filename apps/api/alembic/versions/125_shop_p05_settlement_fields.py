"""P05 清结算：结转字段 + 订单 settled_at。

Revision ID: 125
Revises: 124
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "125"
down_revision = "124"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("shop_settlement_batches") as batch:
        batch.add_column(
            sa.Column("opening_balance_cents", sa.BigInteger(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("period_net_cents", sa.BigInteger(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("offset_by_batch_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("offset_settled_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("confirm_remark", sa.Text(), nullable=True))
        batch.create_index("ix_shop_settlement_batches_offset_by_batch_id", ["offset_by_batch_id"])

    with op.batch_alter_table("shop_settlement_items") as batch:
        batch.add_column(sa.Column("source_batch_id", sa.Uuid(), nullable=True))
        batch.create_index("ix_shop_settlement_items_source_batch_id", ["source_batch_id"])

    with op.batch_alter_table("shop_orders") as batch:
        batch.add_column(sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_shop_orders_settled_at", ["settled_at"])

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE shop_settlement_batches SET period_net_cents = net_amount_cents "
            "WHERE period_net_cents = 0"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("shop_orders") as batch:
        batch.drop_index("ix_shop_orders_settled_at")
        batch.drop_column("settled_at")
    with op.batch_alter_table("shop_settlement_items") as batch:
        batch.drop_index("ix_shop_settlement_items_source_batch_id")
        batch.drop_column("source_batch_id")
    with op.batch_alter_table("shop_settlement_batches") as batch:
        batch.drop_index("ix_shop_settlement_batches_offset_by_batch_id")
        batch.drop_column("confirm_remark")
        batch.drop_column("offset_settled_at")
        batch.drop_column("offset_by_batch_id")
        batch.drop_column("period_net_cents")
        batch.drop_column("opening_balance_cents")
