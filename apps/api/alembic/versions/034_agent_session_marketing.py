"""034 normalize legacy agent session industry_code to marketing

Revision ID: 034
Revises: 033
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE agent_sessions
            SET industry_code = 'marketing'
            WHERE industry_code IN ('finance', 'legal', '')
               OR industry_code IS NULL
            """
        )
    )


def downgrade() -> None:
    pass
