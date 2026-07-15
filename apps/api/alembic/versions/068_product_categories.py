"""068 product_categories + products.category_id (v1.0 P0)

Revision ID: 068
Revises: 067
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "068"
down_revision: Union[str, None] = "067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["product_categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_categories_tenant_id", "product_categories", ["tenant_id"])
    op.create_index("ix_product_categories_parent_id", "product_categories", ["parent_id"])

    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(sa.Column("category_id", sa.Uuid(), nullable=True))
        batch_op.create_index("ix_products_category_id", ["category_id"])
        batch_op.create_foreign_key(
            "fk_products_category_id",
            "product_categories",
            ["category_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_constraint("fk_products_category_id", type_="foreignkey")
        batch_op.drop_index("ix_products_category_id")
        batch_op.drop_column("category_id")
    op.drop_index("ix_product_categories_parent_id", table_name="product_categories")
    op.drop_index("ix_product_categories_tenant_id", table_name="product_categories")
    op.drop_table("product_categories")
