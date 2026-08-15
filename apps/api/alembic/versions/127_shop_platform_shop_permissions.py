"""P08-B：users.platform_shop_permissions 微调有效集。

Revision ID: 127
Revises: 126
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "127"
down_revision = "126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("platform_shop_permissions", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("platform_shop_permissions")
