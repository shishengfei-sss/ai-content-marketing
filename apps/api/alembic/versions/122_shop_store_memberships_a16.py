"""A16：shop_store_memberships + 角色启用标志。

Revision ID: 122
Revises: 121
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "122"
down_revision = "121"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_store_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["tenant_roles.id"]),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_shop_store_memberships_user_tenant"),
    )
    op.create_index("ix_shop_store_memberships_tenant_id", "shop_store_memberships", ["tenant_id"])
    op.create_index("ix_shop_store_memberships_user_id", "shop_store_memberships", ["user_id"])
    op.create_index("ix_shop_store_memberships_shop_id", "shop_store_memberships", ["shop_id"])

    with op.batch_alter_table("shop_tenant_settings") as batch:
        batch.add_column(
            sa.Column(
                "disabled_shop_role_codes",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("shop_tenant_settings") as batch:
        batch.drop_column("disabled_shop_role_codes")
    op.drop_table("shop_store_memberships")
