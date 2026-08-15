"""108 shop payment configs / payments / logs (M3)

Revision ID: 108
Revises: 107
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "108"
down_revision: Union[str, None] = "107"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shop_payment_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("merchant_id", sa.Uuid(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("wx_mch_id", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("wx_app_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("wx_api_key_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("wx_cert_sn", sa.String(length=64), nullable=True),
        sa.Column("wx_cert_pem_encrypted", sa.Text(), nullable=True),
        sa.Column("wx_notify_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("onboarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("onboarded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["merchant_id"], ["shop_merchant_accounts.id"]),
        sa.ForeignKeyConstraint(["onboarded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "shop_id", name="uq_shop_payment_configs_tenant_shop"),
    )
    op.create_index("ix_shop_payment_configs_merchant_id", "shop_payment_configs", ["merchant_id"])
    op.create_index("ix_shop_payment_configs_tenant_id", "shop_payment_configs", ["tenant_id"])
    op.create_index("ix_shop_payment_configs_shop_id", "shop_payment_configs", ["shop_id"])
    op.create_index("ix_shop_payment_configs_status", "shop_payment_configs", ["status"])

    op.create_table(
        "shop_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("prepay_id", sa.String(length=64), nullable=True),
        sa.Column("wx_transaction_id", sa.String(length=64), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fail_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["order_id"], ["shop_orders.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_shop_payments_order_id"),
    )
    op.create_index("ix_shop_payments_order_id", "shop_payments", ["order_id"])
    op.create_index("ix_shop_payments_tenant_id", "shop_payments", ["tenant_id"])
    op.create_index("ix_shop_payments_shop_id", "shop_payments", ["shop_id"])
    op.create_index("ix_shop_payments_status", "shop_payments", ["status"])
    op.create_index("ix_shop_payments_wx_transaction_id", "shop_payments", ["wx_transaction_id"])

    op.create_table(
        "shop_payment_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.String(length=30), nullable=False),
        sa.Column("wx_transaction_id", sa.String(length=64), nullable=True),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ok"),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["order_id"], ["shop_orders.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_payment_logs_order_id", "shop_payment_logs", ["order_id"])
    op.create_index("ix_shop_payment_logs_tenant_id", "shop_payment_logs", ["tenant_id"])
    op.create_index("ix_shop_payment_logs_event", "shop_payment_logs", ["event"])


def downgrade() -> None:
    op.drop_table("shop_payment_logs")
    op.drop_table("shop_payments")
    op.drop_table("shop_payment_configs")
