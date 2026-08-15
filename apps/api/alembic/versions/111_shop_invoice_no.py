"""111 shop invoice_no + submitted default (A13)

Revision ID: 111
Revises: 110
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "111"
down_revision: Union[str, None] = "110"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("shop_invoice_requests") as batch:
        batch.add_column(sa.Column("invoice_no", sa.String(length=64), nullable=True))
    # pending → submitted（对齐 PRD A13）
    op.execute("UPDATE shop_invoice_requests SET status = 'submitted' WHERE status = 'pending'")


def downgrade() -> None:
    op.execute("UPDATE shop_invoice_requests SET status = 'pending' WHERE status = 'submitted'")
    with op.batch_alter_table("shop_invoice_requests") as batch:
        batch.drop_column("invoice_no")
