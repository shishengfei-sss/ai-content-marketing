"""050 contacts is_decision_maker -> contact_role (v0.9 P0)

Revision ID: 050
Revises: 049
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "050"
down_revision: Union[str, None] = "049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("contacts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("contact_role", sa.String(length=50), nullable=True))

    # 数据迁移：原决策人 -> 决策者
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE contacts SET contact_role = '决策者' "
            "WHERE is_decision_maker IS TRUE"
        )
    )

    with op.batch_alter_table("contacts", schema=None) as batch_op:
        batch_op.drop_column("is_decision_maker")


def downgrade() -> None:
    with op.batch_alter_table("contacts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_decision_maker",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE contacts SET is_decision_maker = true "
            "WHERE contact_role = '决策者'"
        )
    )

    with op.batch_alter_table("contacts", schema=None) as batch_op:
        batch_op.drop_column("contact_role")
