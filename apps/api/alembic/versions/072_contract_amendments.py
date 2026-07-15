"""072 contract_amendments (v1.0 P1)

Revision ID: 072
Revises: 071
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "072"
down_revision: Union[str, None] = "071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contract_amendments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("parent_contract_id", sa.Uuid(), nullable=False),
        sa.Column("amendment_number", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("change_type", sa.String(length=30), nullable=False),
        sa.Column("original_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("amount_delta", sa.Numeric(14, 2), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["parent_contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "amendment_number", name="uq_contract_amendments_tenant_number"),
    )
    op.create_index("ix_contract_amendments_tenant_id", "contract_amendments", ["tenant_id"])
    op.create_index("ix_contract_amendments_parent_contract_id", "contract_amendments", ["parent_contract_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_amendments_parent_contract_id", table_name="contract_amendments")
    op.drop_index("ix_contract_amendments_tenant_id", table_name="contract_amendments")
    op.drop_table("contract_amendments")
