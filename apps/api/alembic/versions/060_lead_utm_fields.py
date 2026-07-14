"""060 lead UTM / source_detail / acquisition_cost (v0.9 P2-05)

Revision ID: 060
Revises: 059
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "060"
down_revision: Union[str, None] = "059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("leads", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_detail", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("utm_source", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("utm_medium", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("utm_campaign", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("landing_url", sa.String(length=500), nullable=True))
        batch_op.add_column(
            sa.Column("acquisition_cost", sa.Numeric(precision=14, scale=2), nullable=True)
        )
        batch_op.create_index("ix_leads_utm_source", ["utm_source"])
        batch_op.create_index("ix_leads_utm_campaign", ["utm_campaign"])


def downgrade() -> None:
    with op.batch_alter_table("leads", schema=None) as batch_op:
        batch_op.drop_index("ix_leads_utm_campaign")
        batch_op.drop_index("ix_leads_utm_source")
        batch_op.drop_column("acquisition_cost")
        batch_op.drop_column("landing_url")
        batch_op.drop_column("utm_campaign")
        batch_op.drop_column("utm_medium")
        batch_op.drop_column("utm_source")
        batch_op.drop_column("source_detail")
