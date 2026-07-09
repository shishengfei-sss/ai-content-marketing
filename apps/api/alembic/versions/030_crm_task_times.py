"""030 CRM task planned/actual times

Revision ID: 030
Revises: 029
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("crm_tasks", sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("crm_tasks", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("crm_tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("crm_tasks", "completed_at")
    op.drop_column("crm_tasks", "started_at")
    op.drop_column("crm_tasks", "planned_start_at")
