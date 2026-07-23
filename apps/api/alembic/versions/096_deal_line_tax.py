"""096 deal_line_items tax_rate + tax_amount (align with quote)

Revision ID: 096
Revises: 095
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "096"
down_revision: Union[str, None] = "095"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("deal_line_items")}
    with op.batch_alter_table("deal_line_items") as batch_op:
        if "tax_rate" not in cols:
            batch_op.add_column(sa.Column("tax_rate", sa.Numeric(5, 2), nullable=True))
        if "tax_amount" not in cols:
            batch_op.add_column(sa.Column("tax_amount", sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("deal_line_items") as batch_op:
        batch_op.drop_column("tax_amount")
        batch_op.drop_column("tax_rate")
