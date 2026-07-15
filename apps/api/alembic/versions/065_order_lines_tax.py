"""065 order_lines tax_rate / tax_amount (v1.0 P0)

Revision ID: 065
Revises: 064
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "065"
down_revision: Union[str, None] = "064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("order_lines", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tax_rate", sa.Numeric(5, 2), nullable=True))
        batch_op.add_column(sa.Column("tax_amount", sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("order_lines", schema=None) as batch_op:
        batch_op.drop_column("tax_amount")
        batch_op.drop_column("tax_rate")
