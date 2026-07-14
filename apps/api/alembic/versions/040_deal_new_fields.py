"""040 deal new fields: description/next_step/deal_type/priority/competitor/contact_role (v0.8 deal P0)

Revision ID: 040
Revises: 039
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("deals", sa.Column("next_step", sa.String(length=200), nullable=True))
    op.add_column("deals", sa.Column("deal_type", sa.String(length=20), nullable=True))
    op.add_column(
        "deals",
        sa.Column("priority", sa.String(length=10), nullable=False, server_default="medium"),
    )
    op.add_column("deals", sa.Column("competitor", sa.String(length=200), nullable=True))
    op.add_column("deals", sa.Column("contact_role", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "contact_role")
    op.drop_column("deals", "competitor")
    op.drop_column("deals", "priority")
    op.drop_column("deals", "deal_type")
    op.drop_column("deals", "next_step")
    op.drop_column("deals", "description")
