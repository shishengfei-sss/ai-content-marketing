"""020 agent workflow step agent_code (v0.4 C5)

Revision ID: 020
Revises: 019
Create Date: 2026-07-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_workflow_steps",
        sa.Column("agent_code", sa.String(30), nullable=False, server_default="creator"),
    )


def downgrade() -> None:
    op.drop_column("agent_workflow_steps", "agent_code")
