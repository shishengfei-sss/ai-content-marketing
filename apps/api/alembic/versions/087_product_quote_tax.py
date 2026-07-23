"""087 products tax fields + quote_lines tax (v1.5)

Revision ID: 087
Revises: 086
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "087"
down_revision: Union[str, None] = "086"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    prod_cols = {c["name"] for c in inspector.get_columns("products")}
    with op.batch_alter_table("products") as batch_op:
        if "default_tax_rate" not in prod_cols:
            batch_op.add_column(sa.Column("default_tax_rate", sa.Numeric(5, 2), nullable=True))
        if "price_includes_tax" not in prod_cols:
            batch_op.add_column(
                sa.Column("price_includes_tax", sa.Boolean(), nullable=False, server_default=sa.text("false"))
            )

    ql_cols = {c["name"] for c in inspector.get_columns("quote_lines")}
    with op.batch_alter_table("quote_lines") as batch_op:
        if "tax_rate" not in ql_cols:
            batch_op.add_column(sa.Column("tax_rate", sa.Numeric(5, 2), nullable=True))
        if "tax_amount" not in ql_cols:
            batch_op.add_column(sa.Column("tax_amount", sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("quote_lines") as batch_op:
        batch_op.drop_column("tax_amount")
        batch_op.drop_column("tax_rate")
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_column("price_includes_tax")
        batch_op.drop_column("default_tax_rate")
