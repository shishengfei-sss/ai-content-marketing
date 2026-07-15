"""069 order revision fields (v1.0 P1)

Revision ID: 069
Revises: 068
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "069"
down_revision: Union[str, None] = "068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_order_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("revision_reason", sa.String(length=500), nullable=True))
        batch_op.create_index("ix_orders_parent_order_id", ["parent_order_id"])
        batch_op.create_foreign_key(
            "fk_orders_parent_order_id",
            "orders",
            ["parent_order_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_constraint("fk_orders_parent_order_id", type_="foreignkey")
        batch_op.drop_index("ix_orders_parent_order_id")
        batch_op.drop_column("revision_reason")
        batch_op.drop_column("version")
        batch_op.drop_column("parent_order_id")
