"""100 shop merchant tables + demo seed (content acquisition shop Phase1)

Revision ID: 100
Revises: 099
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "100"
down_revision: Union[str, None] = "099"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shop_onboarding_applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("initiator", sa.String(length=20), nullable=False, server_default="ops_assisted"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("legal_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("display_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("contact_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("contact_mobile", sa.String(length=11), nullable=False, server_default=""),
        sa.Column("qualification_files", sa.JSON(), nullable=False),
        sa.Column("ocr_results", sa.JSON(), nullable=False),
        sa.Column("reject_code", sa.String(length=30), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("merchant_id", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_onboarding_applications_tenant_id", "shop_onboarding_applications", ["tenant_id"])
    op.create_index("ix_shop_onboarding_applications_status", "shop_onboarding_applications", ["status"])

    op.create_table(
        "shop_merchant_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("onboarding_application_id", sa.Uuid(), nullable=True),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("display_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("contact_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("contact_mobile", sa.String(length=11), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("onboarding_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fee_tier", sa.String(length=20), nullable=True),
        sa.Column("current_subscription_id", sa.Uuid(), nullable=True),
        sa.Column("account_manager_user_id", sa.Uuid(), nullable=True),
        sa.Column("plan_label", sa.String(length=100), nullable=True),
        sa.Column("plan_status", sa.String(length=30), nullable=True),
        sa.Column("benefits_until", sa.Date(), nullable=True),
        sa.Column("store_count_active", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("store_quota", sa.Integer(), nullable=True),
        sa.Column("has_pending_renewal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_manager_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["onboarding_application_id"], ["shop_onboarding_applications.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_shop_merchant_accounts_tenant_id"),
    )
    op.create_index("ix_shop_merchant_accounts_tenant_id", "shop_merchant_accounts", ["tenant_id"])
    op.create_index("ix_shop_merchant_accounts_status", "shop_merchant_accounts", ["status"])
    op.create_index("ix_shop_merchant_accounts_plan_status", "shop_merchant_accounts", ["plan_status"])
    op.create_index(
        "ix_shop_merchant_accounts_account_manager_user_id",
        "shop_merchant_accounts",
        ["account_manager_user_id"],
    )

    op.create_table(
        "shop_merchant_service_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("merchant_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="logged"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operator_user_id", sa.Uuid(), nullable=False),
        sa.Column("related_onboarding_id", sa.Uuid(), nullable=True),
        sa.Column("related_subscription_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["merchant_id"], ["shop_merchant_accounts.id"]),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_merchant_service_logs_merchant_id", "shop_merchant_service_logs", ["merchant_id"])
    op.create_index("ix_shop_merchant_service_logs_tenant_id", "shop_merchant_service_logs", ["tenant_id"])
    op.create_index("ix_shop_merchant_service_logs_type", "shop_merchant_service_logs", ["type"])
    op.create_index("ix_shop_merchant_service_logs_status", "shop_merchant_service_logs", ["status"])

    _seed_demo_data()


def _seed_demo_data() -> None:
    conn = op.get_bind()
    tenants = conn.execute(sa.text("SELECT id, name FROM tenants ORDER BY created_at LIMIT 6")).fetchall()
    if not tenants:
        return
    admin = conn.execute(
        sa.text("SELECT id FROM users WHERE role = 'platform_admin' ORDER BY created_at LIMIT 1")
    ).fetchone()
    admin_id = str(admin[0]) if admin else None
    now = datetime.now(timezone.utc)
    soon = (now + timedelta(days=5)).date()
    expired = (now - timedelta(days=30)).date()
    future = (now + timedelta(days=365)).date()

    samples = [
        ("enterprise", "active", "基础版", "active", future, 2, 3, False),
        ("enterprise", "active", "旗舰版", "expiring_soon", soon, 3, 5, True),
        ("personal", "suspended", "免费版", "active", None, 1, 1, False),
        ("enterprise", "active", "免费版（已到期）", "expired", expired, 2, 1, False),
    ]
    merchant_ids: list[str] = []
    for i, (entity_type, status, plan_label, plan_status, benefits_until, stores, quota, pending) in enumerate(samples):
        if i >= len(tenants):
            break
        tid, tname = tenants[i]
        mid = str(uuid.uuid4())
        merchant_ids.append(mid)
        conn.execute(
            sa.text(
                """
                INSERT INTO shop_merchant_accounts (
                    id, tenant_id, entity_type, legal_name, display_name, contact_name, contact_mobile,
                    status, onboarding_approved_at, account_manager_user_id, plan_label, plan_status,
                    benefits_until, store_count_active, store_quota, has_pending_renewal
                ) VALUES (
                    :id, :tid, :entity_type, :legal_name, :display_name, :contact_name, :mobile,
                    :status, :approved_at, :manager_id, :plan_label, :plan_status,
                    :benefits_until, :stores, :quota, :pending
                )
                """
            ),
            {
                "id": mid,
                "tid": str(tid),
                "entity_type": entity_type,
                "legal_name": f"{tname}主体",
                "display_name": tname,
                "contact_name": "联系人",
                "mobile": "13800000000",
                "status": status,
                "approved_at": now.isoformat(),
                "manager_id": admin_id,
                "plan_label": plan_label,
                "plan_status": plan_status,
                "benefits_until": benefits_until.isoformat() if benefits_until else None,
                "stores": stores,
                "quota": quota,
                "pending": pending,
            },
        )

    if len(tenants) > len(samples):
        tid, tname = tenants[len(samples)]
        conn.execute(
            sa.text(
                """
                INSERT INTO shop_onboarding_applications (
                    id, tenant_id, entity_type, initiator, status, legal_name, display_name,
                    contact_name, contact_mobile, qualification_files, ocr_results, submitted_at
                ) VALUES (
                    :id, :tid, 'enterprise', 'merchant_self', 'pending', :legal_name, :display_name,
                    '联系人', '13900000000', '{}', '[]', :submitted_at
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tid": str(tid),
                "legal_name": f"{tname}主体",
                "display_name": tname,
                "submitted_at": now.isoformat(),
            },
        )

    if merchant_ids and admin_id:
        conn.execute(
            sa.text(
                """
                INSERT INTO shop_merchant_service_logs (
                    id, merchant_id, tenant_id, type, status, content, payload_json, operator_user_id
                ) VALUES (
                    :id, :mid, :tid, 'renewal_request', 'pending', :content, :payload, :operator_id
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "mid": merchant_ids[1] if len(merchant_ids) > 1 else merchant_ids[0],
                "tid": str(tenants[1][0] if len(tenants) > 1 else tenants[0][0]),
                "content": "旗舰版续 1 年；客户已确认预算",
                "payload": '{"target_plan":"旗舰版","purchase_mode":"replace","customer_confirmed":true}',
                "operator_id": admin_id,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_shop_merchant_service_logs_status", table_name="shop_merchant_service_logs")
    op.drop_index("ix_shop_merchant_service_logs_type", table_name="shop_merchant_service_logs")
    op.drop_index("ix_shop_merchant_service_logs_tenant_id", table_name="shop_merchant_service_logs")
    op.drop_index("ix_shop_merchant_service_logs_merchant_id", table_name="shop_merchant_service_logs")
    op.drop_table("shop_merchant_service_logs")
    op.drop_index("ix_shop_merchant_accounts_account_manager_user_id", table_name="shop_merchant_accounts")
    op.drop_index("ix_shop_merchant_accounts_plan_status", table_name="shop_merchant_accounts")
    op.drop_index("ix_shop_merchant_accounts_status", table_name="shop_merchant_accounts")
    op.drop_index("ix_shop_merchant_accounts_tenant_id", table_name="shop_merchant_accounts")
    op.drop_table("shop_merchant_accounts")
    op.drop_index("ix_shop_onboarding_applications_status", table_name="shop_onboarding_applications")
    op.drop_index("ix_shop_onboarding_applications_tenant_id", table_name="shop_onboarding_applications")
    op.drop_table("shop_onboarding_applications")
