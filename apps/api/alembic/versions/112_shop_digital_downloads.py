"""112 shop digital download counters (M09)

Revision ID: 112
Revises: 111
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "112"
down_revision: Union[str, None] = "111"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shop_digital_downloads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.String(length=64), nullable=False),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["buyer_id"], ["shop_buyers.id"]),
        sa.ForeignKeyConstraint(["entitlement_id"], ["shop_entitlements.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entitlement_id", "file_id", name="uq_shop_digital_dl_ent_file"),
    )
    op.create_index("ix_shop_digital_downloads_tenant_id", "shop_digital_downloads", ["tenant_id"])
    op.create_index("ix_shop_digital_downloads_buyer_id", "shop_digital_downloads", ["buyer_id"])
    op.create_index("ix_shop_digital_downloads_entitlement_id", "shop_digital_downloads", ["entitlement_id"])


def downgrade() -> None:
    op.drop_index("ix_shop_digital_downloads_entitlement_id", table_name="shop_digital_downloads")
    op.drop_index("ix_shop_digital_downloads_buyer_id", table_name="shop_digital_downloads")
    op.drop_index("ix_shop_digital_downloads_tenant_id", table_name="shop_digital_downloads")
    op.drop_table("shop_digital_downloads")
