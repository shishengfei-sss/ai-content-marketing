"""A15 支付进件表 shop_payment_onboardings。

Revision ID: 120
Revises: 119
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "120"
down_revision = "119"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_payment_onboardings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("merchant_id", sa.Uuid(), nullable=True),
        sa.Column("onboarding_status", sa.String(length=20), nullable=False, server_default="not_submitted"),
        sa.Column("settlement_bank", sa.String(length=100), nullable=True),
        sa.Column("settlement_account", sa.String(length=64), nullable=True),
        sa.Column("settlement_account_name", sa.String(length=200), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("wx_sub_mch_id", sa.String(length=32), nullable=True),
        sa.Column("mch_name", sa.String(length=200), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("entity_snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["merchant_id"], ["shop_merchant_accounts.id"]),
        sa.UniqueConstraint("tenant_id", name="uq_shop_payment_onboardings_tenant"),
    )
    op.create_index("ix_shop_payment_onboardings_tenant_id", "shop_payment_onboardings", ["tenant_id"])
    op.create_index(
        "ix_shop_payment_onboardings_status", "shop_payment_onboardings", ["onboarding_status"]
    )


def downgrade() -> None:
    op.drop_table("shop_payment_onboardings")
