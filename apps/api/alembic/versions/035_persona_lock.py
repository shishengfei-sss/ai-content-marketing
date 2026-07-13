"""035 add agent_sessions.persona_code for persona locking

Revision ID: 035
Revises: 034
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_sessions") as batch:
        batch.add_column(sa.Column("persona_code", sa.String(20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("agent_sessions") as batch:
        batch.drop_column("persona_code")
