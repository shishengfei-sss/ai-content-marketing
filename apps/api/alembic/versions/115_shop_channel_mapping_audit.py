"""A14：映射外部审核/阻断原因字段。

Revision ID: 115
Revises: 114
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "115"
down_revision = "114"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shop_channel_mappings",
        sa.Column("external_audit_status", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "shop_channel_mappings",
        sa.Column("mount_blocked_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "shop_channel_mappings",
        sa.Column("mount_blocked_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "shop_channel_mappings",
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 回填：已挂载→approved；已阻断→rejected；暂停→approved；其余 submitted/空
    op.execute(
        """
        UPDATE shop_channel_mappings
        SET external_audit_status = CASE
            WHEN status IN ('mapped', 'paused') THEN 'approved'
            WHEN status = 'blocked' THEN 'rejected'
            WHEN status = 'pending' THEN 'submitted'
            ELSE external_audit_status
        END
        WHERE external_audit_status IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("shop_channel_mappings", "blocked_at")
    op.drop_column("shop_channel_mappings", "mount_blocked_reason")
    op.drop_column("shop_channel_mappings", "mount_blocked_code")
    op.drop_column("shop_channel_mappings", "external_audit_status")
