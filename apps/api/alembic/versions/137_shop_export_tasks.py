"""开票等列表导出任务表。对照 01#a13 导出。

Revision ID: 137
Revises: 136
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "137"
down_revision = "136"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_export_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("resource", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("file_name", sa.String(length=200), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_export_tasks_tenant_id", "shop_export_tasks", ["tenant_id"])
    op.create_index("ix_shop_export_tasks_resource", "shop_export_tasks", ["resource"])


def downgrade() -> None:
    op.drop_index("ix_shop_export_tasks_resource", table_name="shop_export_tasks")
    op.drop_index("ix_shop_export_tasks_tenant_id", table_name="shop_export_tasks")
    op.drop_table("shop_export_tasks")
