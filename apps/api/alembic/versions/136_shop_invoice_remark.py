"""开票申请开具备注落库。对照 01#a13c。

Revision ID: 136
Revises: 135
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "136"
down_revision = "135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shop_invoice_requests",
        sa.Column("remark", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shop_invoice_requests", "remark")
