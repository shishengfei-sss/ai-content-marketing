"""Agent long-term memory facts (v0.4 LM1)

Revision ID: 014
Revises: 012
Create Date: 2026-07-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_memory_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="preference"),
        sa.Column("fact_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="explicit"),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_memory_facts_user_scope", "agent_memory_facts", ["user_id", "scope"])
    op.create_index("ix_agent_memory_facts_tenant_scope", "agent_memory_facts", ["tenant_id", "scope"])


def downgrade() -> None:
    op.drop_index("ix_agent_memory_facts_tenant_scope", table_name="agent_memory_facts")
    op.drop_index("ix_agent_memory_facts_user_scope", table_name="agent_memory_facts")
    op.drop_table("agent_memory_facts")
