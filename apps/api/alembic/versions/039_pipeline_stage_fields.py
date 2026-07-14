"""039 pipeline stage color / is_closed_stage (v0.8 deal P0)

Revision ID: 039
Revises: 038
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sales_pipeline_stages",
        sa.Column("is_closed_stage", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "sales_pipeline_stages",
        sa.Column("color", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sales_pipeline_stages", "color")
    op.drop_column("sales_pipeline_stages", "is_closed_stage")
