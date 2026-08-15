"""107 shop buyers / orders / entitlements / enrollments / refunds (M5)

Revision ID: 107
Revises: 106
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "107"
down_revision: Union[str, None] = "106"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shop_buyers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("mobile", sa.String(length=11), nullable=True),
        sa.Column("wx_openid", sa.String(length=64), nullable=True),
        sa.Column("nickname", sa.String(length=100), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "mobile", name="uq_shop_buyers_tenant_mobile"),
        sa.UniqueConstraint("tenant_id", "wx_openid", name="uq_shop_buyers_tenant_openid"),
    )
    op.create_index("ix_shop_buyers_tenant_id", "shop_buyers", ["tenant_id"])
    op.create_index("ix_shop_buyers_mobile", "shop_buyers", ["mobile"])
    op.create_index("ix_shop_buyers_wx_openid", "shop_buyers", ["wx_openid"])

    op.create_table(
        "shop_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("product_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("order_no", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_payment"),
        sa.Column("paid_amount_cents", sa.BigInteger(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_channel", sa.String(length=30), nullable=True),
        sa.Column("refund_amount_cents", sa.BigInteger(), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refund_reason", sa.Text(), nullable=True),
        sa.Column("claim_token", sa.String(length=64), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_buyer_id", sa.Uuid(), nullable=True),
        sa.Column("needs_red_flush", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("invoice_status", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="private"),
        sa.Column("wx_transaction_id", sa.String(length=64), nullable=True),
        sa.Column("buyer_mobile_snapshot", sa.String(length=11), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["buyer_id"], ["shop_buyers.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["shop_products.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_no", name="uq_shop_orders_order_no"),
    )
    op.create_index("ix_shop_orders_tenant_id", "shop_orders", ["tenant_id"])
    op.create_index("ix_shop_orders_shop_id", "shop_orders", ["shop_id"])
    op.create_index("ix_shop_orders_buyer_id", "shop_orders", ["buyer_id"])
    op.create_index("ix_shop_orders_product_id", "shop_orders", ["product_id"])
    op.create_index("ix_shop_orders_status", "shop_orders", ["status"])
    op.create_index("ix_shop_orders_wx_transaction_id", "shop_orders", ["wx_transaction_id"])

    op.create_table(
        "shop_entitlements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("remaining_count", sa.Integer(), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["buyer_id"], ["shop_buyers.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["shop_orders.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["shop_products.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_shop_entitlements_order_id"),
    )
    op.create_index("ix_shop_entitlements_tenant_id", "shop_entitlements", ["tenant_id"])
    op.create_index("ix_shop_entitlements_buyer_id", "shop_entitlements", ["buyer_id"])
    op.create_index("ix_shop_entitlements_order_id", "shop_entitlements", ["order_id"])
    op.create_index("ix_shop_entitlements_product_id", "shop_entitlements", ["product_id"])
    op.create_index("ix_shop_entitlements_shop_id", "shop_entitlements", ["shop_id"])
    op.create_index("ix_shop_entitlements_status", "shop_entitlements", ["status"])

    op.create_table(
        "shop_enrollments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("progress_json", sa.JSON(), nullable=False),
        sa.Column("last_learned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["buyer_id"], ["shop_buyers.id"]),
        sa.ForeignKeyConstraint(["entitlement_id"], ["shop_entitlements.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_enrollments_tenant_id", "shop_enrollments", ["tenant_id"])
    op.create_index("ix_shop_enrollments_buyer_id", "shop_enrollments", ["buyer_id"])
    op.create_index("ix_shop_enrollments_entitlement_id", "shop_enrollments", ["entitlement_id"])
    op.create_index("ix_shop_enrollments_course_id", "shop_enrollments", ["course_id"])
    op.create_index("ix_shop_enrollments_status", "shop_enrollments", ["status"])

    op.create_table(
        "shop_refunds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="processing"),
        sa.Column("initiated_by", sa.String(length=20), nullable=False),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("is_partial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("entitlement_revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wx_refund_id", sa.String(length=64), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["shop_orders.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_refunds_order_id", "shop_refunds", ["order_id"])
    op.create_index("ix_shop_refunds_tenant_id", "shop_refunds", ["tenant_id"])
    op.create_index("ix_shop_refunds_status", "shop_refunds", ["status"])


def downgrade() -> None:
    op.drop_table("shop_refunds")
    op.drop_table("shop_enrollments")
    op.drop_table("shop_entitlements")
    op.drop_table("shop_orders")
    op.drop_table("shop_buyers")
