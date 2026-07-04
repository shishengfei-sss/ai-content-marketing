"""account_type on platform_accounts, content_format on contents

Revision ID: 006
Revises: 005
Create Date: 2026-07-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("platform_accounts") as batch_op:
        batch_op.add_column(
            sa.Column("account_type", sa.String(length=20), nullable=False, server_default="service")
        )

    with op.batch_alter_table("contents") as batch_op:
        batch_op.add_column(
            sa.Column("content_format", sa.String(length=30), nullable=False, server_default="article")
        )

    conn = op.get_bind()
    conn.execute(sa.text("UPDATE contents SET content_format = 'video_script' WHERE platform = 'douyin'"))
    conn.execute(sa.text("UPDATE contents SET content_format = 'note' WHERE platform = 'xhs'"))


def downgrade() -> None:
    with op.batch_alter_table("contents") as batch_op:
        batch_op.drop_column("content_format")

    with op.batch_alter_table("platform_accounts") as batch_op:
        batch_op.drop_column("account_type")
