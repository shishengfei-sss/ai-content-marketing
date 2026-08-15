"""110 shop public channel mappings / webhook / claim (M7)

Revision ID: 110
Revises: 109
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "110"
down_revision: Union[str, None] = "109"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shop_channel_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("enabled_combos", sa.JSON(), nullable=False),
        sa.Column("douyin_shop_id", sa.String(length=64), nullable=True),
        sa.Column("douyin_webhook_secret", sa.String(length=128), nullable=True),
        sa.Column("douyin_configured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_shop_channel_settings_tenant"),
    )
    op.create_index("ix_shop_channel_settings_tenant_id", "shop_channel_settings", ["tenant_id"])

    op.create_table(
        "shop_channel_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("channel_product_id", sa.String(length=64), nullable=False),
        sa.Column("channel_product_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="mapped"),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["shop_products.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "channel", "channel_product_id", name="uq_shop_channel_mappings_ch_pid"
        ),
    )
    op.create_index("ix_shop_channel_mappings_tenant_id", "shop_channel_mappings", ["tenant_id"])
    op.create_index("ix_shop_channel_mappings_product_id", "shop_channel_mappings", ["product_id"])
    op.create_index("ix_shop_channel_mappings_status", "shop_channel_mappings", ["status"])

    op.create_table(
        "shop_channel_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=True),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["shop_products.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_channel_audit_logs_tenant_id", "shop_channel_audit_logs", ["tenant_id"])
    op.create_index("ix_shop_channel_audit_logs_event", "shop_channel_audit_logs", ["event"])

    op.create_table(
        "shop_webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "event_id", name="uq_shop_webhook_events_ch_eid"),
    )
    op.create_index("ix_shop_webhook_events_tenant_id", "shop_webhook_events", ["tenant_id"])

    op.create_table(
        "shop_claim_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_mobile", sa.String(length=11), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_buyer_id", sa.Uuid(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["claimed_buyer_id"], ["shop_buyers.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["shop_orders.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_shop_claim_tokens_token"),
    )
    op.create_index("ix_shop_claim_tokens_order_id", "shop_claim_tokens", ["order_id"])
    op.create_index("ix_shop_claim_tokens_token", "shop_claim_tokens", ["token"])
    op.create_index("ix_shop_claim_tokens_status", "shop_claim_tokens", ["status"])

    op.create_table(
        "shop_sms_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=True),
        sa.Column("buyer_mobile", sa.String(length=11), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="sent"),
        sa.Column("provider_msg_id", sa.String(length=64), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_sms_logs_tenant_id", "shop_sms_logs", ["tenant_id"])
    op.create_index("ix_shop_sms_logs_buyer_mobile", "shop_sms_logs", ["buyer_mobile"])


def downgrade() -> None:
    op.drop_table("shop_sms_logs")
    op.drop_table("shop_claim_tokens")
    op.drop_table("shop_webhook_events")
    op.drop_table("shop_channel_audit_logs")
    op.drop_table("shop_channel_mappings")
    op.drop_table("shop_channel_settings")
