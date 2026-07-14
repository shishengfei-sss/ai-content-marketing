"""057 entity_team_members + migrate deal_team_members (v0.9 P1)

Revision ID: 057
Revises: 056
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "057"
down_revision: Union[str, None] = "056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entity_team_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "entity_type", "entity_id", "user_id", name="uq_entity_team_member"
        ),
    )
    op.create_index("ix_entity_team_members_tenant_id", "entity_team_members", ["tenant_id"])
    op.create_index(
        "ix_entity_team_members_entity", "entity_team_members", ["entity_type", "entity_id"]
    )

    # 从 045 deal_team_members 复制（保留原表，双写过渡）
    op.execute(
        """
        INSERT INTO entity_team_members (id, tenant_id, entity_type, entity_id, user_id, role, joined_at)
        SELECT id, tenant_id, 'deal', deal_id, user_id, role, joined_at
        FROM deal_team_members
        """
    )


def downgrade() -> None:
    op.drop_index("ix_entity_team_members_entity", table_name="entity_team_members")
    op.drop_index("ix_entity_team_members_tenant_id", table_name="entity_team_members")
    op.drop_table("entity_team_members")
