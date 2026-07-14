"""047 sales_pipeline_stages max_stay_days (v0.8 deal P2-01)

Revision ID: 047
Revises: 046
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "047"
down_revision: Union[str, None] = "046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sales_pipeline_stages", schema=None) as batch_op:
        batch_op.add_column(sa.Column("max_stay_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sales_pipeline_stages", schema=None) as batch_op:
        batch_op.drop_column("max_stay_days")
