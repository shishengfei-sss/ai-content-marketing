"""048 lead new fields: title/lead_score/department/country (v0.9 lead P0)

Revision ID: 048
Revises: 047
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "048"
down_revision: Union[str, None] = "047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("leads", schema=None) as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("lead_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("department", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("country", sa.String(length=50), nullable=True, server_default="中国")
        )


def downgrade() -> None:
    with op.batch_alter_table("leads", schema=None) as batch_op:
        batch_op.drop_column("country")
        batch_op.drop_column("department")
        batch_op.drop_column("lead_score")
        batch_op.drop_column("title")
