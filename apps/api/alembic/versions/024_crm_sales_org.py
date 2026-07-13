"""024 CRM sales territories and membership sales profiles (v0.5 1b)

Revision ID: 024
Revises: 023
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales_territories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("manager_membership_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["sales_territories.id"]),
        sa.ForeignKeyConstraint(["manager_membership_id"], ["tenant_memberships.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_territories_tenant_id", "sales_territories", ["tenant_id"])
    op.create_index("ix_sales_territories_parent_id", "sales_territories", ["parent_id"])

    op.create_table(
        "membership_sales_profile",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("primary_territory_id", sa.Uuid(), nullable=True),
        sa.Column("reports_to_membership_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["membership_id"], ["tenant_memberships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["primary_territory_id"], ["sales_territories.id"]),
        sa.ForeignKeyConstraint(["reports_to_membership_id"], ["tenant_memberships.id"]),
        sa.PrimaryKeyConstraint("membership_id"),
    )


def downgrade() -> None:
    op.drop_table("membership_sales_profile")
    op.drop_index("ix_sales_territories_parent_id", table_name="sales_territories")
    op.drop_index("ix_sales_territories_tenant_id", table_name="sales_territories")
    op.drop_table("sales_territories")
