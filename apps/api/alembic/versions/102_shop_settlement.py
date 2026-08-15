"""102 shop settlement batches + items (content acquisition shop Phase1 P05)

Revision ID: 102
Revises: 101
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "102"
down_revision: Union[str, None] = "101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shop_settlement_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("batch_no", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("gross_amount_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("platform_fee_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("refund_reversal_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("net_amount_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transfer_voucher_url", sa.Text(), nullable=True),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("fail_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_no", name="uq_shop_settlement_batches_batch_no"),
    )
    op.create_index("ix_shop_settlement_batches_tenant_id", "shop_settlement_batches", ["tenant_id"])
    op.create_index("ix_shop_settlement_batches_shop_id", "shop_settlement_batches", ["shop_id"])
    op.create_index("ix_shop_settlement_batches_status", "shop_settlement_batches", ["status"])
    op.create_index(
        "ix_shop_settlement_batches_tenant_period",
        "shop_settlement_batches",
        ["tenant_id", "period_end"],
    )

    # order_id / refund_id 暂不建 FK：shop_orders / shop_refunds 表尚未落地（后续迁移补约束）
    op.create_table(
        "shop_settlement_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("item_type", sa.String(length=20), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("refund_id", sa.Uuid(), nullable=True),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("fee_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["shop_settlement_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_settlement_items_batch_id", "shop_settlement_items", ["batch_id"])
    op.create_index("ix_shop_settlement_items_order_id", "shop_settlement_items", ["order_id"])
    op.create_index("ix_shop_settlement_items_refund_id", "shop_settlement_items", ["refund_id"])


def downgrade() -> None:
    op.drop_index("ix_shop_settlement_items_refund_id", table_name="shop_settlement_items")
    op.drop_index("ix_shop_settlement_items_order_id", table_name="shop_settlement_items")
    op.drop_index("ix_shop_settlement_items_batch_id", table_name="shop_settlement_items")
    op.drop_table("shop_settlement_items")
    op.drop_index("ix_shop_settlement_batches_tenant_period", table_name="shop_settlement_batches")
    op.drop_index("ix_shop_settlement_batches_status", table_name="shop_settlement_batches")
    op.drop_index("ix_shop_settlement_batches_shop_id", table_name="shop_settlement_batches")
    op.drop_index("ix_shop_settlement_batches_tenant_id", table_name="shop_settlement_batches")
    op.drop_table("shop_settlement_batches")
