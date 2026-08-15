"""P02-E / P02-B-T：预分配管家 + 商家标签。

Revision ID: 128
Revises: 127
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "128"
down_revision = "127"
branch_labels = None
depends_on = None

_SEED_TAGS = (
    ("续费意向", "orange"),
    ("高价值", "gray"),
    ("需回访", "blue"),
    ("华东区", "purple"),
    ("对公客户", "green"),
)


def upgrade() -> None:
    op.create_table(
        "shop_tenant_prospect_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("account_manager_user_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["account_manager_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_shop_tenant_prospect_assignments_tenant"),
    )
    op.create_index(
        "ix_shop_tenant_prospect_assignments_account_manager_user_id",
        "shop_tenant_prospect_assignments",
        ["account_manager_user_id"],
    )

    op.create_table(
        "shop_merchant_tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False, server_default="blue"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_shop_merchant_tags_name"),
    )

    op.create_table(
        "shop_merchant_tag_links",
        sa.Column("merchant_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("tagged_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["merchant_id"], ["shop_merchant_accounts.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["shop_merchant_tags.id"]),
        sa.ForeignKeyConstraint(["tagged_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("merchant_id", "tag_id"),
        sa.UniqueConstraint("merchant_id", "tag_id", name="uq_shop_merchant_tag_links_pair"),
    )

    tags = sa.table(
        "shop_merchant_tags",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("color", sa.String()),
        sa.column("usage_count", sa.Integer()),
        sa.column("is_archived", sa.Boolean()),
    )
    op.bulk_insert(
        tags,
        [
            {
                "id": uuid.uuid4(),
                "name": name,
                "color": color,
                "usage_count": 0,
                "is_archived": False,
            }
            for name, color in _SEED_TAGS
        ],
    )


def downgrade() -> None:
    op.drop_table("shop_merchant_tag_links")
    op.drop_table("shop_merchant_tags")
    op.drop_index(
        "ix_shop_tenant_prospect_assignments_account_manager_user_id",
        table_name="shop_tenant_prospect_assignments",
    )
    op.drop_table("shop_tenant_prospect_assignments")
