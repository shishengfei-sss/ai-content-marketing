"""027 CRM entity schema and view preferences (v0.5 2b)

Revision ID: 027
Revises: 026
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entity_field_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("field_key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("field_type", sa.String(30), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_unique", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("options", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("default_value", sa.String(500), nullable=True),
        sa.Column("placeholder", sa.String(200), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("show_in_list_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("list_width", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("validation", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("storage", sa.String(10), nullable=False, server_default="seed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "entity_type", "field_key", name="uq_entity_field_tenant_type_key"),
    )
    op.create_index(
        "ix_entity_field_definitions_tenant_entity",
        "entity_field_definitions",
        ["tenant_id", "entity_type"],
    )

    op.create_table(
        "user_entity_view_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("view_kind", sa.String(20), nullable=False, server_default="list"),
        sa.Column("columns", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "tenant_id",
            "entity_type",
            "view_kind",
            name="uq_user_entity_view_pref",
        ),
    )
    op.create_index(
        "ix_user_entity_view_preferences_user",
        "user_entity_view_preferences",
        ["user_id", "tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_entity_view_preferences_user", table_name="user_entity_view_preferences")
    op.drop_table("user_entity_view_preferences")
    op.drop_index("ix_entity_field_definitions_tenant_entity", table_name="entity_field_definitions")
    op.drop_table("entity_field_definitions")
