"""092 creator org snapshot on CRM entities

Revision ID: 092
Revises: 091

线索/客户/商机等：创建时落库创建人汇报上级；区域仍用 territory_id（创建时默认写入创建人主地区）。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "092"
down_revision: Union[str, None] = "091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("leads", "customers", "deals", "marketing_campaigns", "crm_tasks")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("manager_user_id", sa.Uuid(), nullable=True))
        op.create_index(f"ix_{table}_manager_user_id", table, ["manager_user_id"])


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_manager_user_id", table_name=table)
        op.drop_column(table, "manager_user_id")
