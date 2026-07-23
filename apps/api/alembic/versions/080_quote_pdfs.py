"""080 CPQ: quote_pdfs 异步 PDF 元数据表

Revision ID: 080
Revises: 079
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "080"
down_revision: Union[str, None] = "079"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quote_pdfs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("quote_id", sa.Uuid(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="generating"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quote_pdfs_tenant_id", "quote_pdfs", ["tenant_id"])
    op.create_index("ix_quote_pdfs_quote_id", "quote_pdfs", ["quote_id"])


def downgrade() -> None:
    op.drop_index("ix_quote_pdfs_quote_id", table_name="quote_pdfs")
    op.drop_index("ix_quote_pdfs_tenant_id", table_name="quote_pdfs")
    op.drop_table("quote_pdfs")
