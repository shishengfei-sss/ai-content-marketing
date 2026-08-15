"""P06：平台渠道凭据加密表。对照 04#platform_channel_credentials。

Revision ID: 130
Revises: 129
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "130"
down_revision = "129"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_channel_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("secret_enc", sa.Text(), nullable=False, server_default=""),
        sa.Column("prev_secret_enc", sa.Text(), nullable=True),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", name="uq_platform_channel_credentials_channel"),
    )
    op.create_index(
        "ix_platform_channel_credentials_channel",
        "platform_channel_credentials",
        ["channel"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_platform_channel_credentials_channel", table_name="platform_channel_credentials")
    op.drop_table("platform_channel_credentials")
