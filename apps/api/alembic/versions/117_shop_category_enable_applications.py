"""P04-D 类目启用审批单。

Revision ID: 117
Revises: 116
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "117"
down_revision = "116"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_category_enable_applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("proposed_platform_fee_bps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("proposed_require_qualifications", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("submitted_by", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["category_id"], ["shop_platform_categories.id"]),
    )
    op.create_index(
        "ix_shop_category_enable_applications_category_id",
        "shop_category_enable_applications",
        ["category_id"],
    )
    op.create_index(
        "ix_shop_category_enable_applications_status",
        "shop_category_enable_applications",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_shop_category_enable_applications_status", table_name="shop_category_enable_applications")
    op.drop_index("ix_shop_category_enable_applications_category_id", table_name="shop_category_enable_applications")
    op.drop_table("shop_category_enable_applications")
