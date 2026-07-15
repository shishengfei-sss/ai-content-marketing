"""077 price_books + entries + product stats (v1.0 P1)

Revision ID: 077
Revises: 076
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "077"
down_revision: Union[str, None] = "076"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("total_ordered_quantity", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "products",
        sa.Column("total_revenue", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column("products", sa.Column("last_order_date", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "price_books",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_books_tenant_id", "price_books", ["tenant_id"])

    op.create_table(
        "price_book_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("price_book_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("min_quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("customer_levels", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["price_book_id"], ["price_books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_book_entries_tenant_id", "price_book_entries", ["tenant_id"])
    op.create_index("ix_price_book_entries_price_book_id", "price_book_entries", ["price_book_id"])
    op.create_index("ix_price_book_entries_product_id", "price_book_entries", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_price_book_entries_product_id", table_name="price_book_entries")
    op.drop_index("ix_price_book_entries_price_book_id", table_name="price_book_entries")
    op.drop_index("ix_price_book_entries_tenant_id", table_name="price_book_entries")
    op.drop_table("price_book_entries")
    op.drop_index("ix_price_books_tenant_id", table_name="price_books")
    op.drop_table("price_books")
    op.drop_column("products", "last_order_date")
    op.drop_column("products", "total_revenue")
    op.drop_column("products", "total_ordered_quantity")
