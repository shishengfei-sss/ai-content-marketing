"""028 CRM entity list views (v0.5 2c)

Revision ID: 028
Revises: 027
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entity_list_views",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("filters", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("sort", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("columns", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("search_q", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_entity_list_views_tenant_entity",
        "entity_list_views",
        ["tenant_id", "entity_type"],
    )
    op.create_index(
        "ix_entity_list_views_owner",
        "entity_list_views",
        ["owner_user_id", "tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_entity_list_views_owner", table_name="entity_list_views")
    op.drop_index("ix_entity_list_views_tenant_entity", table_name="entity_list_views")
    op.drop_table("entity_list_views")
