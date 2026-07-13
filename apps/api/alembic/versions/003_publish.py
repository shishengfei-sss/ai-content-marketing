"""publish fields and platform accounts

Revision ID: 003
Revises: 002
Create Date: 2026-07-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("contents") as batch_op:
        batch_op.add_column(sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("publish_error", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("mock_read_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("preview_path", sa.String(length=500), nullable=True))

    op.create_table(
        "publish_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["content_id"], ["contents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_publish_logs_content_id"),
        "publish_logs",
        ["content_id"],
        unique=False,
    )

    op.create_table(
        "platform_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False),
        sa.Column("account_name", sa.String(length=200), nullable=False),
        sa.Column("is_mock", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "platform", name="uq_platform_accounts_tenant_platform"),
    )


def downgrade() -> None:
    op.drop_table("platform_accounts")
    op.drop_index(op.f("ix_publish_logs_content_id"), table_name="publish_logs")
    op.drop_table("publish_logs")
    with op.batch_alter_table("contents") as batch_op:
        batch_op.drop_column("preview_path")
        batch_op.drop_column("mock_read_count")
        batch_op.drop_column("publish_error")
        batch_op.drop_column("published_at")
        batch_op.drop_column("scheduled_at")
