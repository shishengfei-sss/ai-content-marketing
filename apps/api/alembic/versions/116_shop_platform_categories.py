"""P04 平台类目 + 商品 category_id。

Revision ID: 116
Revises: 115
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "116"
down_revision = "115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_platform_categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("code_source", sa.String(length=20), nullable=False, server_default="auto"),
        sa.Column("platform_fee_bps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settlement_rule", sa.String(length=40), nullable=False, server_default="standard"),
        sa.Column("require_qualifications", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="enabled"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("code", name="uq_shop_platform_categories_code"),
    )
    op.create_index("ix_shop_platform_categories_parent_id", "shop_platform_categories", ["parent_id"])
    op.create_index("ix_shop_platform_categories_status", "shop_platform_categories", ["status"])

    op.add_column("shop_products", sa.Column("category_id", sa.Uuid(), nullable=True))
    op.create_index("ix_shop_products_category_id", "shop_products", ["category_id"])

    # 种子类目（平台级）
    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    root_v = str(uuid.uuid4())
    child_v = str(uuid.uuid4())
    root_e = str(uuid.uuid4())
    root_h = str(uuid.uuid4())
    rows = [
        (root_v, None, "职业培训", "cat.vocational", "auto", 200, "standard", '["办学许可证", "备案"]', "enabled", None),
        (child_v, root_v, "销售话术", "cat.vocational.sales", "auto", 200, "standard", "[]", "enabled", None),
        (root_e, None, "企业服务", "cat.enterprise", "auto", 180, "standard", "[]", "enabled", None),
        (root_h, None, "医疗健康", "cat.health", "auto", 0, "standard", "[]", "blocked", "禁入类目示例"),
    ]
    for r in rows:
        conn.execute(
            sa.text(
                """
                INSERT INTO shop_platform_categories
                (id, parent_id, name, code, code_source, platform_fee_bps, settlement_rule,
                 require_qualifications, status, description, created_at, updated_at)
                VALUES
                (:id, :parent_id, :name, :code, :code_source, :fee, :rule,
                 :qual, :status, :description, :now, :now)
                """
            ),
            {
                "id": r[0],
                "parent_id": r[1],
                "name": r[2],
                "code": r[3],
                "code_source": r[4],
                "fee": r[5],
                "rule": r[6],
                "qual": r[7],
                "status": r[8],
                "description": r[9],
                "now": now,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_shop_products_category_id", table_name="shop_products")
    op.drop_column("shop_products", "category_id")
    op.drop_index("ix_shop_platform_categories_status", table_name="shop_platform_categories")
    op.drop_index("ix_shop_platform_categories_parent_id", table_name="shop_platform_categories")
    op.drop_table("shop_platform_categories")
