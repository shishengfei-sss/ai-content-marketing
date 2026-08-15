"""P02-B 商家操作日志独立表。对照 06#p02b-audit · 04 shop_audit_logs。

Revision ID: 134
Revises: 133
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "134"
down_revision = "133"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("merchant_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("operator_user_id", sa.Uuid(), nullable=True),
        sa.Column("operator_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["merchant_id"], ["shop_merchant_accounts.id"]),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_audit_logs_tenant_id", "shop_audit_logs", ["tenant_id"])
    op.create_index("ix_shop_audit_logs_merchant_id", "shop_audit_logs", ["merchant_id"])
    op.create_index("ix_shop_audit_logs_action", "shop_audit_logs", ["action"])

    conn = op.get_bind()
    users = {
        str(r[0]): (r[1] or r[2] or "系统")
        for r in conn.execute(sa.text("SELECT id, display_name, phone FROM users")).fetchall()
    }

    sub_action = {
        "manual": ("订阅开通", "订阅台账"),
        "renew": ("订阅续费", "订阅台账"),
        "upgrade": ("订阅换档", "订阅台账"),
        "addon": ("叠加开通", "订阅台账"),
        "trial": ("订阅开通", "入驻审核"),
        "purchase": ("订阅开通", "订阅台账"),
    }
    insert = sa.text(
        "INSERT INTO shop_audit_logs "
        "(id, tenant_id, merchant_id, action, summary, operator_user_id, operator_name, source, created_at) "
        "VALUES (:id, :tenant_id, :merchant_id, :action, :summary, :operator_user_id, :operator_name, :source, :created_at)"
    )
    merchants = {
        str(r[0]): r[1]
        for r in conn.execute(sa.text("SELECT tenant_id, id FROM shop_merchant_accounts")).fetchall()
    }
    subs = conn.execute(
        sa.text(
            "SELECT id, tenant_id, source, subscription_no, plan_snapshot, operator_id, created_at "
            "FROM shop_merchant_subscriptions"
        )
    ).fetchall()
    for row in subs:
        _sid, tenant_id, source, sub_no, snap, operator_id, created_at = row
        action, src_label = sub_action.get(source or "", ("订阅开通", "订阅台账"))
        plan_name = ""
        if isinstance(snap, dict):
            plan_name = snap.get("plan_name") or snap.get("plan_code") or ""
        elif isinstance(snap, str) and snap.startswith("{"):
            import json

            try:
                parsed = json.loads(snap)
                plan_name = parsed.get("plan_name") or parsed.get("plan_code") or ""
            except json.JSONDecodeError:
                plan_name = ""
        summary = " · ".join(p for p in (plan_name, sub_no) if p)
        oid = str(operator_id) if operator_id else None
        conn.execute(
            insert,
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(tenant_id),
                "merchant_id": merchants.get(str(tenant_id)),
                "action": action,
                "summary": summary,
                "operator_user_id": oid,
                "operator_name": users.get(oid or "", "系统"),
                "source": src_label,
                "created_at": created_at,
            },
        )

    logs = conn.execute(
        sa.text(
            "SELECT tenant_id, merchant_id, type, content, payload_json, operator_user_id, created_at "
            "FROM shop_merchant_service_logs "
            "WHERE type IN ('status_change', 'note', 'audit')"
        )
    ).fetchall()
    import json

    for tenant_id, merchant_id, typ, content, payload, operator_id, created_at in logs:
        data = payload if isinstance(payload, dict) else {}
        if isinstance(payload, str):
            try:
                data = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                data = {}
        action = None
        source = "商家列表"
        if typ == "status_change":
            to_status = data.get("to")
            action = {"suspended": "暂停", "active": "恢复", "closed": "清退"}.get(to_status, "状态变更")
            source = "商家列表"
        elif typ == "note" and data.get("action") == "assign_manager":
            action = "分配管家"
            source = "商家列表"
        elif typ == "audit" and data.get("action") == "reveal_sensitive":
            action = "查看敏感信息"
            source = "商家详情"
        if not action:
            continue
        oid = str(operator_id) if operator_id else None
        conn.execute(
            insert,
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(tenant_id),
                "merchant_id": str(merchant_id) if merchant_id else merchants.get(str(tenant_id)),
                "action": action,
                "summary": content or "",
                "operator_user_id": oid,
                "operator_name": users.get(oid or "", "系统"),
                "source": source,
                "created_at": created_at,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_shop_audit_logs_action", table_name="shop_audit_logs")
    op.drop_index("ix_shop_audit_logs_merchant_id", table_name="shop_audit_logs")
    op.drop_index("ix_shop_audit_logs_tenant_id", table_name="shop_audit_logs")
    op.drop_table("shop_audit_logs")
