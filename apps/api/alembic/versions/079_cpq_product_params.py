"""079 CPQ W1-2: products.cpq_enabled + product_params + param_pricings + quotes.cpq_config_snapshot

Revision ID: 079
Revises: 078
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "079"
down_revision: Union[str, None] = "078"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("cpq_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("quotes", sa.Column("cpq_config_snapshot", sa.JSON(), nullable=True))

    op.create_table(
        "product_params",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("param_name", sa.String(length=100), nullable=False),
        sa.Column("param_type", sa.String(length=20), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_params_tenant_id", "product_params", ["tenant_id"])
    op.create_index("ix_product_params_product_id", "product_params", ["product_id"])

    op.create_table(
        "param_pricings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("param_id", sa.Uuid(), nullable=False),
        sa.Column("option_value", sa.String(length=100), nullable=False),
        sa.Column("price_adjustment_type", sa.String(length=20), nullable=False),
        sa.Column("price_adjustment_value", sa.Numeric(10, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["param_id"], ["product_params.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_param_pricings_param_id", "param_pricings", ["param_id"])


def downgrade() -> None:
    op.drop_index("ix_param_pricings_param_id", table_name="param_pricings")
    op.drop_table("param_pricings")
    op.drop_index("ix_product_params_product_id", table_name="product_params")
    op.drop_index("ix_product_params_tenant_id", table_name="product_params")
    op.drop_table("product_params")
    op.drop_column("quotes", "cpq_config_snapshot")
    op.drop_column("products", "cpq_enabled")
