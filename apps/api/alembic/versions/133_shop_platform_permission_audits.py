"""P08-B：保存商城角色/权限写审计表。对照 06#p08b。

Revision ID: 133
Revises: 132
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "133"
down_revision = "132"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_platform_permission_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=False),
        sa.Column("operator_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("role_from", sa.String(length=50), nullable=True),
        sa.Column("role_to", sa.String(length=50), nullable=True),
        sa.Column("permissions_from", sa.JSON(), nullable=False),
        sa.Column("permissions_to", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_shop_platform_permission_audits_target_user_id",
        "shop_platform_permission_audits",
        ["target_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shop_platform_permission_audits_target_user_id",
        table_name="shop_platform_permission_audits",
    )
    op.drop_table("shop_platform_permission_audits")
