"""063 order_approval_rules (v1.0 P0)

Revision ID: 063
Revises: 062
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "063"
down_revision: Union[str, None] = "062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_approval_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("min_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("max_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("approver_role", sa.String(length=50), nullable=False),
        sa.Column("approval_type", sa.String(length=20), nullable=False, server_default="sequential"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_approval_rules_tenant_id", "order_approval_rules", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_order_approval_rules_tenant_id", table_name="order_approval_rules")
    op.drop_table("order_approval_rules")
