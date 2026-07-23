"""084 编号规则增加 suffix 后缀

Revision ID: 084
Revises: 083
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "084"
down_revision: Union[str, None] = "083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "entity_number_rules",
        sa.Column("suffix", sa.String(length=10), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("entity_number_rules", "suffix")
