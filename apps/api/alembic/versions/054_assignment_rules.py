"""054 assignment_rules (v0.9 P1)

Revision ID: 054
Revises: 053
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "054"
down_revision: Union[str, None] = "053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assignment_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("condition_json", sa.JSON(), nullable=False),
        sa.Column("assign_type", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
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
    op.create_index("ix_assignment_rules_tenant_id", "assignment_rules", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_assignment_rules_tenant_id", table_name="assignment_rules")
    op.drop_table("assignment_rules")
