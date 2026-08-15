"""114 shop columns / lessons / digital packages (A04-A06)

Revision ID: 114
Revises: 113
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "114"
down_revision: Union[str, None] = "113"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shop_columns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("intro", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_columns_tenant_id", "shop_columns", ["tenant_id"])
    op.create_index("ix_shop_columns_shop_id", "shop_columns", ["shop_id"])
    op.create_index("ix_shop_columns_status", "shop_columns", ["status"])

    op.create_table(
        "shop_lessons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("column_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("media_type", sa.String(length=20), nullable=False),
        sa.Column("media_id", sa.String(length=64), nullable=True),
        sa.Column("media_url", sa.String(length=500), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_trial", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("trial_seconds", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["column_id"], ["shop_columns.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_lessons_tenant_id", "shop_lessons", ["tenant_id"])
    op.create_index("ix_shop_lessons_column_id", "shop_lessons", ["column_id"])
    op.create_index("ix_shop_lessons_status", "shop_lessons", ["status"])

    op.create_table(
        "shop_digital_packages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("deliver_mode", sa.String(length=20), nullable=False),
        sa.Column("max_downloads", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shop_stores.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_digital_packages_tenant_id", "shop_digital_packages", ["tenant_id"])
    op.create_index("ix_shop_digital_packages_shop_id", "shop_digital_packages", ["shop_id"])
    op.create_index("ix_shop_digital_packages_status", "shop_digital_packages", ["status"])

    op.create_table(
        "shop_digital_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("previewable", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["shop_digital_packages.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_digital_assets_tenant_id", "shop_digital_assets", ["tenant_id"])
    op.create_index("ix_shop_digital_assets_package_id", "shop_digital_assets", ["package_id"])


def downgrade() -> None:
    op.drop_index("ix_shop_digital_assets_package_id", table_name="shop_digital_assets")
    op.drop_index("ix_shop_digital_assets_tenant_id", table_name="shop_digital_assets")
    op.drop_table("shop_digital_assets")
    op.drop_index("ix_shop_digital_packages_status", table_name="shop_digital_packages")
    op.drop_index("ix_shop_digital_packages_shop_id", table_name="shop_digital_packages")
    op.drop_index("ix_shop_digital_packages_tenant_id", table_name="shop_digital_packages")
    op.drop_table("shop_digital_packages")
    op.drop_index("ix_shop_lessons_status", table_name="shop_lessons")
    op.drop_index("ix_shop_lessons_column_id", table_name="shop_lessons")
    op.drop_index("ix_shop_lessons_tenant_id", table_name="shop_lessons")
    op.drop_table("shop_lessons")
    op.drop_index("ix_shop_columns_status", table_name="shop_columns")
    op.drop_index("ix_shop_columns_shop_id", table_name="shop_columns")
    op.drop_index("ix_shop_columns_tenant_id", table_name="shop_columns")
    op.drop_table("shop_columns")
