"""055 addresses (v0.9 P1)

Revision ID: 055
Revises: 054
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "055"
down_revision: Union[str, None] = "054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "addresses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("address_type", sa.String(length=30), nullable=False, server_default="office"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("province", sa.String(length=50), nullable=True),
        sa.Column("city", sa.String(length=50), nullable=True),
        sa.Column("district", sa.String(length=50), nullable=True),
        sa.Column("address", sa.String(length=300), nullable=False),
        sa.Column("zip_code", sa.String(length=20), nullable=True),
        sa.Column("contact_name", sa.String(length=100), nullable=True),
        sa.Column("contact_phone", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_addresses_tenant_id", "addresses", ["tenant_id"])
    op.create_index("ix_addresses_entity", "addresses", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_addresses_entity", table_name="addresses")
    op.drop_index("ix_addresses_tenant_id", table_name="addresses")
    op.drop_table("addresses")
