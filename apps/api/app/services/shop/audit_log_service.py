"""P02-B 商家操作日志。对照 06#p02b-audit · 04 shop_audit_logs。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import User
from app.models.shop import ShopAuditLog

ACTION_SUBSCRIBE = "订阅开通"
ACTION_RENEW = "订阅续费"
ACTION_REPLACE = "订阅换档"
ACTION_ADDON = "叠加开通"
ACTION_ONBOARD = "入驻通过"
ACTION_ASSIGN = "分配管家"
ACTION_SUSPEND = "暂停"
ACTION_RESUME = "恢复"
ACTION_CLOSE = "清退"
ACTION_REVEAL = "查看敏感信息"

SOURCE_SUBSCRIPTION = "订阅台账"
SOURCE_ONBOARDING = "入驻审核"
SOURCE_MERCHANT_LIST = "商家列表"
SOURCE_MERCHANT_DETAIL = "商家详情"

SUBSCRIPTION_AUDIT = {
    "trial": (ACTION_SUBSCRIBE, SOURCE_ONBOARDING),
    "manual": (ACTION_SUBSCRIBE, SOURCE_SUBSCRIPTION),
    "purchase": (ACTION_SUBSCRIBE, SOURCE_SUBSCRIPTION),
    "renew": (ACTION_RENEW, SOURCE_SUBSCRIPTION),
    "upgrade": (ACTION_REPLACE, SOURCE_SUBSCRIPTION),
    "addon": (ACTION_ADDON, SOURCE_SUBSCRIPTION),
}

STATUS_AUDIT = {
    "suspended": ACTION_SUSPEND,
    "active": ACTION_RESUME,
    "closed": ACTION_CLOSE,
}


def record_merchant_audit(
    db: Session,
    *,
    tenant_id: UUID,
    merchant_id: UUID | None,
    action: str,
    summary: str,
    source: str,
    operator: User | None = None,
    operator_user_id: UUID | None = None,
) -> ShopAuditLog:
    oid = operator_user_id or (operator.id if operator is not None else None)
    name = ""
    if operator is not None:
        name = operator.display_name or operator.phone or ""
    elif oid is not None:
        u = db.query(User).filter(uuid_eq(User.id, oid)).first()
        name = (u.display_name or u.phone or "") if u else ""
    row = ShopAuditLog(
        tenant_id=tenant_id,
        merchant_id=merchant_id,
        action=action,
        summary=(summary or "").strip(),
        operator_user_id=oid,
        operator_name=name or "系统",
        source=source,
    )
    db.add(row)
    return row
