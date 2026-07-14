"""042 attachments table (v0.8 deal P1-02)

Revision ID: 042
Revises: 041
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=True),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attachments_tenant_id", "attachments", ["tenant_id"])
    op.create_index("ix_attachments_entity", "attachments", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_attachments_entity", table_name="attachments")
    op.drop_index("ix_attachments_tenant_id", table_name="attachments")
    op.drop_table("attachments")
