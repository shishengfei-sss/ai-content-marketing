"""104 shop plan features / subscription plans / merchant subscriptions (M1)

Revision ID: 104
Revises: 103
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "104"
down_revision: Union[str, None] = "103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ALL_ENTITY = ["personal", "individual_business", "enterprise"]
PAID_ENTITY = ["individual_business", "enterprise"]


def upgrade() -> None:
    op.create_table(
        "shop_plan_features",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("node_type", sa.String(length=10), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("category", sa.String(length=20), nullable=True),
        sa.Column("value_type", sa.String(length=20), nullable=True),
        sa.Column("aggregate_mode", sa.String(length=10), nullable=True),
        sa.Column("usage_period", sa.String(length=20), nullable=True),
        sa.Column("meter_key", sa.String(length=64), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["shop_plan_features.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_shop_plan_features_code"),
    )
    op.create_index("ix_shop_plan_features_parent_id", "shop_plan_features", ["parent_id"])
    op.create_index("ix_shop_plan_features_node_type", "shop_plan_features", ["node_type"])
    op.create_index("ix_shop_plan_features_is_active", "shop_plan_features", ["is_active"])

    op.create_table(
        "shop_subscription_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("plan_type", sa.String(length=20), nullable=False, server_default="main"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("stackable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("replace_group", sa.String(length=40), nullable=True),
        sa.Column("billing_period", sa.String(length=20), nullable=False, server_default="yearly"),
        sa.Column("price_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("quotas", sa.JSON(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("usage_limits", sa.JSON(), nullable=False),
        sa.Column("allowed_entity_types", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_shop_subscription_plans_code"),
        sa.UniqueConstraint("name", name="uq_shop_subscription_plans_name"),
    )
    op.create_index("ix_shop_subscription_plans_plan_type", "shop_subscription_plans", ["plan_type"])
    op.create_index("ix_shop_subscription_plans_is_active", "shop_subscription_plans", ["is_active"])
    op.create_index("ix_shop_subscription_plans_replace_group", "shop_subscription_plans", ["replace_group"])

    op.create_table(
        "shop_merchant_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_no", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purchase_mode", sa.String(length=20), nullable=False, server_default="stack"),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("previous_subscription_id", sa.Uuid(), nullable=True),
        sa.Column("plan_snapshot", sa.JSON(), nullable=False),
        sa.Column("catalog_price_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("paid_amount_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["shop_subscription_plans.id"]),
        sa.ForeignKeyConstraint(["previous_subscription_id"], ["shop_merchant_subscriptions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscription_no", name="uq_shop_merchant_subscriptions_no"),
    )
    op.create_index("ix_shop_merchant_subscriptions_tenant_id", "shop_merchant_subscriptions", ["tenant_id"])
    op.create_index("ix_shop_merchant_subscriptions_plan_id", "shop_merchant_subscriptions", ["plan_id"])
    op.create_index("ix_shop_merchant_subscriptions_status", "shop_merchant_subscriptions", ["status"])
    op.create_index(
        "ix_shop_merchant_subscriptions_expires_at", "shop_merchant_subscriptions", ["expires_at"]
    )

    op.create_table(
        "shop_merchant_feature_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("feature_code", sa.String(length=64), nullable=False),
        sa.Column("period_key", sa.String(length=20), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "feature_code",
            "period_key",
            name="uq_shop_merchant_feature_usage_period",
        ),
    )
    op.create_index("ix_shop_merchant_feature_usage_tenant_id", "shop_merchant_feature_usage", ["tenant_id"])

    _seed_feature_dictionary()
    _seed_subscription_plans()


def _seed_feature_dictionary() -> None:
    conn = op.get_bind()
    g_shop = str(uuid.uuid4())
    g_ops = str(uuid.uuid4())
    g_channel = str(uuid.uuid4())
    rows = [
        (g_shop, "group.shop", "店铺与商品", "group", None, 10, None, None, None, None, None, None),
        (
            str(uuid.uuid4()),
            "quota.max_shops",
            "店铺数上限",
            "leaf",
            g_shop,
            10,
            "quota",
            "int",
            "max",
            None,
            None,
            "个",
        ),
        (
            str(uuid.uuid4()),
            "quota.max_products",
            "商品数上限",
            "leaf",
            g_shop,
            20,
            "quota",
            "int",
            "sum",
            None,
            None,
            "个",
        ),
        (g_ops, "group.ops", "运营用量", "group", None, 20, None, None, None, None, None, None),
        (
            str(uuid.uuid4()),
            "usage.product_review_submit",
            "商品提审次数",
            "leaf",
            g_ops,
            10,
            "usage",
            "usage",
            "sum",
            "daily",
            "product.review_submit",
            "次",
        ),
        (
            str(uuid.uuid4()),
            "usage.sms_claim_send",
            "核销短信发送",
            "leaf",
            g_ops,
            20,
            "usage",
            "usage",
            "sum",
            "monthly",
            "sms.claim_send",
            "次",
        ),
        (g_channel, "group.channel", "渠道与功能", "group", None, 30, None, None, None, None, None, None),
        (
            str(uuid.uuid4()),
            "channel.doudian",
            "抖店对接",
            "leaf",
            g_channel,
            10,
            "feature",
            "bool",
            "any",
            None,
            None,
            None,
        ),
        (
            str(uuid.uuid4()),
            "feature.invoice",
            "开票能力",
            "leaf",
            g_channel,
            20,
            "feature",
            "bool",
            "any",
            None,
            None,
            None,
        ),
    ]
    for (
        fid,
        code,
        name,
        node_type,
        parent_id,
        sort_order,
        category,
        value_type,
        aggregate_mode,
        usage_period,
        meter_key,
        unit,
    ) in rows:
        conn.execute(
            sa.text(
                """
                INSERT INTO shop_plan_features (
                    id, code, name, node_type, parent_id, sort_order,
                    category, value_type, aggregate_mode, usage_period, meter_key, unit,
                    description, is_active
                ) VALUES (
                    :id, :code, :name, :node_type, :parent_id, :sort_order,
                    :category, :value_type, :aggregate_mode, :usage_period, :meter_key, :unit,
                    NULL, true
                )
                """
            ),
            {
                "id": fid,
                "code": code,
                "name": name,
                "node_type": node_type,
                "parent_id": parent_id,
                "sort_order": sort_order,
                "category": category,
                "value_type": value_type,
                "aggregate_mode": aggregate_mode,
                "usage_period": usage_period,
                "meter_key": meter_key,
                "unit": unit,
            },
        )


def _seed_subscription_plans() -> None:
    plans_t = sa.table(
        "shop_subscription_plans",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("plan_type", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_public", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
        sa.column("stackable", sa.Boolean()),
        sa.column("replace_group", sa.String()),
        sa.column("billing_period", sa.String()),
        sa.column("price_cents", sa.BigInteger()),
        sa.column("quotas", sa.JSON()),
        sa.column("features", sa.JSON()),
        sa.column("usage_limits", sa.JSON()),
        sa.column("allowed_entity_types", sa.JSON()),
        sa.column("description", sa.Text()),
    )
    plans = [
        {
            "id": uuid.uuid4(),
            "code": "free",
            "name": "免费版",
            "plan_type": "main",
            "sort_order": 10,
            "is_public": True,
            "is_active": True,
            "stackable": False,
            "replace_group": "main",
            "billing_period": "yearly",
            "price_cents": 0,
            "quotas": {"quota.max_shops": 1, "quota.max_products": 20},
            "features": {"channel.doudian": False, "feature.invoice": False},
            "usage_limits": {"usage.product_review_submit": 3},
            "allowed_entity_types": ALL_ENTITY,
            "description": "入驻默认档；个人主体可用",
        },
        {
            "id": uuid.uuid4(),
            "code": "basic",
            "name": "基础版",
            "plan_type": "main",
            "sort_order": 20,
            "is_public": True,
            "is_active": True,
            "stackable": False,
            "replace_group": "main",
            "billing_period": "yearly",
            "price_cents": 980000,
            "quotas": {"quota.max_shops": 3, "quota.max_products": 200},
            "features": {"channel.doudian": True, "feature.invoice": False},
            "usage_limits": {"usage.product_review_submit": 20},
            "allowed_entity_types": PAID_ENTITY,
            "description": "主推商用档；P03 试用开通此模板",
        },
        {
            "id": uuid.uuid4(),
            "code": "flagship",
            "name": "旗舰版",
            "plan_type": "main",
            "sort_order": 30,
            "is_public": True,
            "is_active": True,
            "stackable": False,
            "replace_group": "main",
            "billing_period": "yearly",
            "price_cents": 2980000,
            "quotas": {"quota.max_shops": "unlimited", "quota.max_products": "unlimited"},
            "features": {"channel.doudian": True, "feature.invoice": True},
            "usage_limits": {"usage.product_review_submit": "unlimited"},
            "allowed_entity_types": PAID_ENTITY,
            "description": "高配额主套餐",
        },
        {
            "id": uuid.uuid4(),
            "code": "addon_sms_500",
            "name": "短信加购 +500/月",
            "plan_type": "addon",
            "sort_order": 10,
            "is_public": True,
            "is_active": True,
            "stackable": True,
            "replace_group": None,
            "billing_period": "monthly",
            "price_cents": 19900,
            "quotas": {},
            "features": {},
            "usage_limits": {"usage.sms_claim_send": 500},
            "allowed_entity_types": ALL_ENTITY,
            "description": "可与主套餐叠加",
        },
        {
            "id": uuid.uuid4(),
            "code": "addon_products_20",
            "name": "商品槽 +20",
            "plan_type": "addon",
            "sort_order": 20,
            "is_public": True,
            "is_active": True,
            "stackable": True,
            "replace_group": None,
            "billing_period": "yearly",
            "price_cents": 59900,
            "quotas": {"quota.max_products": 20},
            "features": {},
            "usage_limits": {},
            "allowed_entity_types": ALL_ENTITY,
            "description": "可与主套餐叠加",
        },
    ]
    op.bulk_insert(plans_t, plans)


def downgrade() -> None:
    op.drop_table("shop_merchant_feature_usage")
    op.drop_table("shop_merchant_subscriptions")
    op.drop_table("shop_subscription_plans")
    op.drop_table("shop_plan_features")
