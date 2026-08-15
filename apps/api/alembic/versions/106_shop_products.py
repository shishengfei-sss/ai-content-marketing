"""106 shop products + product reviews (M4)

Revision ID: 106
Revises: 105
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "106"
down_revision: Union[str, None] = "105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shop_products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("subtitle", sa.String(length=300), nullable=True),
        sa.Column("cover_url", sa.String(length=500), nullable=True),
        sa.Column("price_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("line_price_cents", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("ref_type", sa.String(length=30), nullable=True),
        sa.Column("ref_id", sa.Uuid(), nullable=True),
        sa.Column("last_review_id", sa.Uuid(), nullable=True),
        sa.Column("compliance_flags", sa.JSON(), nullable=False),
        sa.Column("refund_policy", sa.String(length=30), nullable=False, server_default="before_fulfill"),
        sa.Column("sales_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_products_tenant_id", "shop_products", ["tenant_id"])
    op.create_index("ix_shop_products_shop_id", "shop_products", ["shop_id"])
    op.create_index("ix_shop_products_status", "shop_products", ["status"])
    op.create_index("ix_shop_products_type", "shop_products", ["type"])

    op.create_table(
        "shop_product_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("auto_result", sa.String(length=20), nullable=False, server_default="pass"),
        sa.Column("auto_flags", sa.JSON(), nullable=False),
        sa.Column("manual_result", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["shop_products.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_product_reviews_product_id", "shop_product_reviews", ["product_id"])
    op.create_index("ix_shop_product_reviews_tenant_id", "shop_product_reviews", ["tenant_id"])
    op.create_index("ix_shop_product_reviews_manual_result", "shop_product_reviews", ["manual_result"])


def downgrade() -> None:
    op.drop_table("shop_product_reviews")
    op.drop_table("shop_products")
