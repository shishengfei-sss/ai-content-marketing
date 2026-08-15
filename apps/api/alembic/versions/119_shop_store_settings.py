"""A19 单店设置表 shop_store_settings。

Revision ID: 119
Revises: 118
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "119"
down_revision = "118"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_store_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("intro", sa.Text(), nullable=True),
        sa.Column("service_phone", sa.String(length=32), nullable=True),
        sa.Column("theme_color", sa.String(length=16), nullable=False, server_default="#1677ff"),
        sa.Column("close_order_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column(
            "default_refund_policy",
            sa.String(length=30),
            nullable=False,
            server_default="before_fulfill",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint("shop_id", name="uq_shop_store_settings_shop_id"),
    )
    op.create_index("ix_shop_store_settings_tenant_id", "shop_store_settings", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_shop_store_settings_tenant_id", table_name="shop_store_settings")
    op.drop_table("shop_store_settings")
