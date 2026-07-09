"""Reset platform LLM provider fake -> deepseek (fake 已停用).

Revision ID: 021
Revises: 020
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE platform_llm_config
            SET provider = 'deepseek',
                base_url = 'https://api.deepseek.com',
                model = 'deepseek-chat'
            WHERE provider = 'fake'
            """
        )
    )


def downgrade() -> None:
    pass
