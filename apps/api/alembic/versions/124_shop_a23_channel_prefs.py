"""A23 公域对接：链路/路径/绑店/验通字段。

Revision ID: 124
Revises: 123
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "124"
down_revision = "123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("shop_channel_settings") as batch:
        batch.add_column(sa.Column("deal_link", sa.String(8), nullable=False, server_default="1"))
        batch.add_column(sa.Column("path_mode", sa.String(8), nullable=False, server_default="A"))
        batch.add_column(
            sa.Column("bind_scope", sa.String(20), nullable=False, server_default="tenant")
        )
        batch.add_column(
            sa.Column("bind_status", sa.String(20), nullable=False, server_default="unbound")
        )
        batch.add_column(sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("webhook_verified", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("webhook_tested_at", sa.DateTime(timezone=True), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE shop_channel_settings SET bind_status = 'available' "
            "WHERE douyin_shop_id IS NOT NULL AND TRIM(douyin_shop_id) != ''"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("shop_channel_settings") as batch:
        batch.drop_column("webhook_tested_at")
        batch.drop_column("webhook_verified")
        batch.drop_column("last_synced_at")
        batch.drop_column("bind_status")
        batch.drop_column("bind_scope")
        batch.drop_column("path_mode")
        batch.drop_column("deal_link")
