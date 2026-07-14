"""041 crm_activities deal link + subject + generic entity (v0.8 deal P1-01)

Revision ID: 041
Revises: 040
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("crm_activities", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deal_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key("fk_crm_activities_deal_id", "deals", ["deal_id"], ["id"])
        batch_op.create_index("ix_crm_activities_deal_id", ["deal_id"])
        batch_op.add_column(sa.Column("subject", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("entity_type", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("entity_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("crm_activities", schema=None) as batch_op:
        batch_op.drop_column("entity_id")
        batch_op.drop_column("entity_type")
        batch_op.drop_column("subject")
        batch_op.drop_index("ix_crm_activities_deal_id")
        batch_op.drop_constraint("fk_crm_activities_deal_id", type_="foreignkey")
        batch_op.drop_column("deal_id")
