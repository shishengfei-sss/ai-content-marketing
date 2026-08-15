"""公域映射落库对接路径 combo，供列表按路径 A/B 筛选。对照 01#a14-list。

Revision ID: 135
Revises: 134
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "135"
down_revision = "134"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shop_channel_mappings",
        sa.Column("combo", sa.String(length=8), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE shop_channel_mappings SET combo = CASE "
            "WHEN channel = 'course_lib' THEN '2A' ELSE '1A' END "
            "WHERE combo IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("shop_channel_mappings", "combo")
