"""089 marketing_campaigns type / expected_leads / location

Revision ID: 089
Revises: 088
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "089"
down_revision: Union[str, None] = "088"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "marketing_campaigns" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("marketing_campaigns")}
    with op.batch_alter_table("marketing_campaigns") as batch_op:
        if "campaign_type" not in cols:
            batch_op.add_column(sa.Column("campaign_type", sa.String(length=30), nullable=True))
        if "expected_leads" not in cols:
            batch_op.add_column(sa.Column("expected_leads", sa.Integer(), nullable=True))
        if "location" not in cols:
            batch_op.add_column(sa.Column("location", sa.String(length=200), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "marketing_campaigns" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("marketing_campaigns")}
    with op.batch_alter_table("marketing_campaigns") as batch_op:
        if "location" in cols:
            batch_op.drop_column("location")
        if "expected_leads" in cols:
            batch_op.drop_column("expected_leads")
        if "campaign_type" in cols:
            batch_op.drop_column("campaign_type")
