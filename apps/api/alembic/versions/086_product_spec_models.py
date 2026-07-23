"""086 product_spec_models + products.spec_model_id (v1.4)

Revision ID: 086
Revises: 085
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "086"
down_revision: Union[str, None] = "085"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "product_spec_models" not in tables:
        op.create_table(
            "product_spec_models",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("code", sa.String(length=50), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "name", name="uq_product_spec_models_tenant_name"),
        )
        op.create_index("ix_product_spec_models_tenant_id", "product_spec_models", ["tenant_id"])

    product_cols = {c["name"] for c in inspector.get_columns("products")}
    if "spec_model_id" not in product_cols:
        with op.batch_alter_table("products", schema=None) as batch_op:
            batch_op.add_column(sa.Column("spec_model_id", sa.Uuid(), nullable=True))
            batch_op.create_index("ix_products_tenant_spec_model", ["tenant_id", "spec_model_id"])
            batch_op.create_foreign_key(
                "fk_products_spec_model_id",
                "product_spec_models",
                ["spec_model_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_constraint("fk_products_spec_model_id", type_="foreignkey")
        batch_op.drop_index("ix_products_tenant_spec_model")
        batch_op.drop_column("spec_model_id")
    op.drop_index("ix_product_spec_models_tenant_id", table_name="product_spec_models")
    op.drop_table("product_spec_models")
