"""070 delivery_notes + delivery_items (v1.0 P1)

Revision ID: 070
Revises: 069
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "070"
down_revision: Union[str, None] = "069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "delivery_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_number", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="preparing"),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tracking_number", sa.String(length=100), nullable=True),
        sa.Column("carrier", sa.String(length=50), nullable=True),
        sa.Column("remark", sa.String(length=500), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "delivery_number", name="uq_delivery_notes_tenant_number"),
    )
    op.create_index("ix_delivery_notes_tenant_id", "delivery_notes", ["tenant_id"])
    op.create_index("ix_delivery_notes_order_id", "delivery_notes", ["order_id"])

    op.create_table(
        "delivery_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_note_id", sa.Uuid(), nullable=False),
        sa.Column("order_line_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["delivery_note_id"], ["delivery_notes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_line_id"], ["order_lines.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_delivery_items_tenant_id", "delivery_items", ["tenant_id"])
    op.create_index("ix_delivery_items_delivery_note_id", "delivery_items", ["delivery_note_id"])


def downgrade() -> None:
    op.drop_index("ix_delivery_items_delivery_note_id", table_name="delivery_items")
    op.drop_index("ix_delivery_items_tenant_id", table_name="delivery_items")
    op.drop_table("delivery_items")
    op.drop_index("ix_delivery_notes_order_id", table_name="delivery_notes")
    op.drop_index("ix_delivery_notes_tenant_id", table_name="delivery_notes")
    op.drop_table("delivery_notes")
