"""036 CRM-2/3 deals/pipelines/quotes/contracts/orders/payments (v0.7)

Revision ID: 036
Revises: 035
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 默认管道 6 阶段（与 §3.20.1 / FR-PIPE 一致）
DEFAULT_STAGES = (
    ("qualifying", 10, 20, False, False),
    ("presenting", 20, 40, False, False),
    ("quoted", 30, 55, False, False),
    ("negotiating", 40, 70, False, False),
    ("closed_won", 50, 100, True, False),
    ("closed_lost", 60, 0, False, True),
)


def _numeric_column(name: str, **kwargs):
    return sa.Column(name, sa.Numeric(14, 2), **kwargs)


def _discount_column(name: str, **kwargs):
    return sa.Column(name, sa.Numeric(5, 2), **kwargs)


def upgrade() -> None:
    # 销售管道
    op.create_table(
        "sales_pipelines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_pipelines_tenant_id", "sales_pipelines", ["tenant_id"])

    # 管道阶段
    op.create_table(
        "sales_pipeline_stages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("probability", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_won_stage", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_lost_stage", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["pipeline_id"], ["sales_pipelines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_pipeline_stages_tenant_id", "sales_pipeline_stages", ["tenant_id"])
    op.create_index("ix_sales_pipeline_stages_pipeline_id", "sales_pipeline_stages", ["pipeline_id"])

    # 商机
    op.create_table(
        "deals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=False),
        _numeric_column("amount", nullable=False, server_default="0"),
        sa.Column("expected_close_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("probability", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("loss_reason", sa.String(200), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("territory_id", sa.Uuid(), nullable=True),
        sa.Column("converted_from_lead_id", sa.Uuid(), nullable=True),
        sa.Column("converted_order_id", sa.Uuid(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["pipeline_id"], ["sales_pipelines.id"]),
        sa.ForeignKeyConstraint(["stage_id"], ["sales_pipeline_stages.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deals_tenant_id", "deals", ["tenant_id"])
    op.create_index("ix_deals_customer_id", "deals", ["customer_id"])
    op.create_index("ix_deals_pipeline_id", "deals", ["pipeline_id"])
    op.create_index("ix_deals_stage_id", "deals", ["stage_id"])
    op.create_index("ix_deals_owner_user_id", "deals", ["owner_user_id"])
    op.create_index("ix_deals_tenant_stage", "deals", ["tenant_id", "stage_id"])
    op.create_index("ix_deals_tenant_owner", "deals", ["tenant_id", "owner_user_id"])

    # 商机阶段流转日志
    op.create_table(
        "deal_stage_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("from_stage_id", sa.Uuid(), nullable=True),
        sa.Column("to_stage_id", sa.Uuid(), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deal_stage_logs_tenant_id", "deal_stage_logs", ["tenant_id"])
    op.create_index("ix_deal_stage_logs_deal_id", "deal_stage_logs", ["deal_id"])

    # 产品目录
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("unit", sa.String(30), nullable=True),
        _numeric_column("list_price", nullable=False, server_default="0"),
        _numeric_column("cost_price", nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_products_tenant_code"),
    )
    op.create_index("ix_products_tenant_id", "products", ["tenant_id"])
    op.create_index("ix_products_tenant_code", "products", ["tenant_id", "code"])

    # 报价
    op.create_table(
        "quotes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("quote_number", sa.String(50), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("subject", sa.String(200), nullable=False),
        _discount_column("discount_rate", nullable=True),
        _numeric_column("total_amount", nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("converted_order_id", sa.Uuid(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quotes_tenant_id", "quotes", ["tenant_id"])
    op.create_index("ix_quotes_deal_id", "quotes", ["deal_id"])
    op.create_index("ix_quotes_customer_id", "quotes", ["customer_id"])
    op.create_index("ix_quotes_owner_user_id", "quotes", ["owner_user_id"])

    # 报价明细
    op.create_table(
        "quote_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("quote_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("unit", sa.String(30), nullable=True),
        _numeric_column("quantity", nullable=False, server_default="1"),
        _numeric_column("unit_price", nullable=False, server_default="0"),
        _discount_column("discount_rate", nullable=True),
        _numeric_column("line_total", nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quote_lines_tenant_id", "quote_lines", ["tenant_id"])
    op.create_index("ix_quote_lines_quote_id", "quote_lines", ["quote_id"])

    # 合同
    op.create_table(
        "contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("contract_number", sa.String(50), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("quote_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("contract_type", sa.String(20), nullable=False, server_default="new"),
        _numeric_column("amount", nullable=False, server_default="0"),
        _numeric_column("signed_amount", nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contracts_tenant_id", "contracts", ["tenant_id"])
    op.create_index("ix_contracts_deal_id", "contracts", ["deal_id"])
    op.create_index("ix_contracts_customer_id", "contracts", ["customer_id"])
    op.create_index("ix_contracts_owner_user_id", "contracts", ["owner_user_id"])

    # 订单
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("order_number", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("deal_id", sa.Uuid(), nullable=True),
        sa.Column("quote_id", sa.Uuid(), nullable=True),
        sa.Column("contract_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        _numeric_column("amount", nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("territory_id", sa.Uuid(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_tenant_id", "orders", ["tenant_id"])
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_deal_id", "orders", ["deal_id"])
    op.create_index("ix_orders_owner_user_id", "orders", ["owner_user_id"])
    op.create_index("ix_orders_tenant_owner", "orders", ["tenant_id", "owner_user_id"])

    # 订单明细
    op.create_table(
        "order_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("unit", sa.String(30), nullable=True),
        _numeric_column("quantity", nullable=False, server_default="1"),
        _numeric_column("unit_price", nullable=False, server_default="0"),
        _discount_column("discount_rate", nullable=True),
        _numeric_column("line_total", nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_lines_tenant_id", "order_lines", ["tenant_id"])
    op.create_index("ix_order_lines_order_id", "order_lines", ["order_id"])

    # 回款计划
    op.create_table(
        "payment_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("installment_no", sa.Integer(), nullable=False),
        sa.Column("plan_date", sa.DateTime(timezone=True), nullable=False),
        _numeric_column("plan_amount", nullable=False, server_default="0"),
        sa.Column("remark", sa.String(500), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_plans_tenant_id", "payment_plans", ["tenant_id"])
    op.create_index("ix_payment_plans_order_id", "payment_plans", ["order_id"])

    # 实际回款
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("payment_number", sa.String(50), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        _numeric_column("amount", nullable=False, server_default="0"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("method", sa.String(20), nullable=False, server_default="bank"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("remark", sa.String(500), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["payment_plans.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_tenant_id", "payments", ["tenant_id"])
    op.create_index("ix_payments_order_id", "payments", ["order_id"])
    op.create_index("ix_payments_owner_user_id", "payments", ["owner_user_id"])
    op.create_index("ix_payments_tenant_order", "payments", ["tenant_id", "order_id"])

    # 为每个存量租户写入默认管道 + 6 阶段
    _seed_default_pipelines()


def _seed_default_pipelines() -> None:
    conn = op.get_bind()
    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()
    for (tenant_id,) in tenants:
        tid = str(tenant_id)
        # 仅当该租户尚无管道时插入
        existing = conn.execute(
            sa.text("SELECT id FROM sales_pipelines WHERE tenant_id = :tid LIMIT 1"),
            {"tid": tid},
        ).fetchone()
        if existing:
            continue
        pipeline_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                """
                INSERT INTO sales_pipelines (id, tenant_id, name, is_default, is_active)
                VALUES (:id, :tid, '标准销售管道', 1, 1)
                """
            ),
            {"id": pipeline_id, "tid": tid},
        )
        for name, sort_order, probability, is_won, is_lost in DEFAULT_STAGES:
            stage_id = str(uuid.uuid4())
            # 中文映射
            cn_name = {
                "qualifying": "需求确认",
                "presenting": "方案演示",
                "quoted": "报价",
                "negotiating": "谈判",
                "closed_won": "赢单",
                "closed_lost": "输单",
            }[name]
            conn.execute(
                sa.text(
                    """
                    INSERT INTO sales_pipeline_stages
                    (id, tenant_id, pipeline_id, name, sort_order, probability,
                     is_won_stage, is_lost_stage, is_active)
                    VALUES (:id, :tid, :pid, :name, :sort, :prob, :won, :lost, 1)
                    """
                ),
                {
                    "id": stage_id,
                    "tid": tid,
                    "pid": pipeline_id,
                    "name": cn_name,
                    "sort": sort_order,
                    "prob": probability,
                    "won": 1 if is_won else 0,
                    "lost": 1 if is_lost else 0,
                },
            )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("payment_plans")
    op.drop_table("order_lines")
    op.drop_table("orders")
    op.drop_table("contracts")
    op.drop_table("quote_lines")
    op.drop_table("quotes")
    op.drop_table("products")
    op.drop_table("deal_stage_logs")
    op.drop_table("deals")
    op.drop_table("sales_pipeline_stages")
    op.drop_table("sales_pipelines")
