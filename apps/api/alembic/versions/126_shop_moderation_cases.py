"""P07 违规稽查工单表。

Revision ID: 126
Revises: 125
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "126"
down_revision = "125"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_moderation_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_no", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("case_type", sa.String(length=40), nullable=False),
        sa.Column("object_type", sa.String(length=30), nullable=False),
        sa.Column("object_ref", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_ref_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("force_off_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("off_reason_type", sa.String(length=40), nullable=True),
        sa.Column("off_reason_text", sa.Text(), nullable=True),
        sa.Column("resolution", sa.String(length=40), nullable=True),
        sa.Column("conclusion", sa.Text(), nullable=True),
        sa.Column("notify_in_app", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notify_sms", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attachments_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("timeline_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["shop_products.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["shop_orders.id"]),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_no", name="uq_shop_moderation_cases_case_no"),
    )
    op.create_index("ix_shop_moderation_cases_tenant_id", "shop_moderation_cases", ["tenant_id"])
    op.create_index("ix_shop_moderation_cases_shop_id", "shop_moderation_cases", ["shop_id"])
    op.create_index("ix_shop_moderation_cases_status", "shop_moderation_cases", ["status"])
    op.create_index("ix_shop_moderation_cases_case_type", "shop_moderation_cases", ["case_type"])
    op.create_index("ix_shop_moderation_cases_reported_at", "shop_moderation_cases", ["reported_at"])
    op.create_index("ix_shop_moderation_cases_product_id", "shop_moderation_cases", ["product_id"])
    op.create_index("ix_shop_moderation_cases_source", "shop_moderation_cases", ["source"])


def downgrade() -> None:
    op.drop_index("ix_shop_moderation_cases_source", table_name="shop_moderation_cases")
    op.drop_index("ix_shop_moderation_cases_product_id", table_name="shop_moderation_cases")
    op.drop_index("ix_shop_moderation_cases_reported_at", table_name="shop_moderation_cases")
    op.drop_index("ix_shop_moderation_cases_case_type", table_name="shop_moderation_cases")
    op.drop_index("ix_shop_moderation_cases_status", table_name="shop_moderation_cases")
    op.drop_index("ix_shop_moderation_cases_shop_id", table_name="shop_moderation_cases")
    op.drop_index("ix_shop_moderation_cases_tenant_id", table_name="shop_moderation_cases")
    op.drop_table("shop_moderation_cases")
