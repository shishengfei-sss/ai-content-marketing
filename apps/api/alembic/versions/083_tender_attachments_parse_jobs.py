"""083 招标附件 + AI 解析任务（tender_attachments / parse_jobs）

Revision ID: 083
Revises: 082
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "083"
down_revision: Union[str, None] = "082"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tender_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform_tender_lead_id", sa.Uuid(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["platform_tender_lead_id"],
            ["platform_tender_leads.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tender_attachments_platform_tender_lead_id",
        "tender_attachments",
        ["platform_tender_lead_id"],
    )

    op.create_table(
        "parse_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attachment_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("confirmed_lead_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["attachment_id"], ["tender_attachments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["confirmed_lead_id"],
            ["platform_tender_leads.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parse_jobs_attachment_id", "parse_jobs", ["attachment_id"])
    op.create_index("ix_parse_jobs_status", "parse_jobs", ["status"])
    op.create_index("ix_parse_jobs_created_at", "parse_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_parse_jobs_created_at", table_name="parse_jobs")
    op.drop_index("ix_parse_jobs_status", table_name="parse_jobs")
    op.drop_index("ix_parse_jobs_attachment_id", table_name="parse_jobs")
    op.drop_table("parse_jobs")
    op.drop_index("ix_tender_attachments_platform_tender_lead_id", table_name="tender_attachments")
    op.drop_table("tender_attachments")
