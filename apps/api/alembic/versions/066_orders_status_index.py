"""066 orders status index (v1.0 P0; status remains String)

Revision ID: 066
Revises: 065

New statuses (app-level): pending_approval / approved / rejected.
No ENUM DDL — Order.status is String(20).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "066"
down_revision: Union[str, None] = "065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_orders_status", "orders", ["status"])


def downgrade() -> None:
    op.drop_index("ix_orders_status", table_name="orders")
