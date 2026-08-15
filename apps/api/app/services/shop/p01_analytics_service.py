"""P01 平台经营看板。对照 PRD 06#p01 · #p01-cs · #p01-finance · §8.14.1。"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import String, cast, false, func, or_
from sqlalchemy.orm import Session

from app.models import User
from app.models.shop import (
    ShopMerchantAccount,
    ShopMerchantServiceLog,
    ShopModerationCase,
    ShopOnboardingApplication,
    ShopOrder,
    ShopProduct,
    ShopSettlementBatch,
)
from app.permissions import PLATFORM_SHOP_ROLE_CS, PLATFORM_SHOP_ROLE_FINANCE
from app.services.platform_shop_service import get_platform_shop_permissions, get_platform_shop_role
from app.services.shop.entitlement_service import TZ_SH
from app.services.shop.merchant_service import resolve_merchant_list_scope

_PAID_STATUSES = ("paid", "claim_pending", "refunding", "refunded")
TZ_CN = TZ_SH

WIDGET_KEYS = (
    "gmv_month_cents",
    "active_merchants",
    "pending_product_reviews",
    "pending_onboarding",
    "open_moderation_cases",
    "pending_renewals",
    "expiring_soon_merchants",
    "my_pending_renewal_requests",
    "settlement_batches_pending",
    "settlement_batches_failed",
    "settled_month_cents",
)

OPS_ORDER = [
    "pending_product_reviews",
    "pending_onboarding",
    "open_moderation_cases",
    "pending_renewals",
    "gmv_month_cents",
    "active_merchants",
]
CS_ORDER = [
    "expiring_soon_merchants",
    "my_pending_renewal_requests",
    "pending_onboarding",
    "gmv_month_cents",
    "active_merchants",
]
FINANCE_ORDER = [
    "settlement_batches_pending",
    "settlement_batches_failed",
    "settled_month_cents",
    "gmv_month_cents",
    "active_merchants",
]


def _now() -> datetime:
    return datetime.now(TZ_CN)


def _month_start(now: datetime | None = None) -> datetime:
    n = now or _now()
    return n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _day_range(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=TZ_CN)
    return start, start + timedelta(days=1)


def resolve_analytics_scope(user: User) -> str:
    """与 P02 同一套 list_all / list_assigned；财务仅有 analytics 时取 all。"""
    perms = set(get_platform_shop_permissions(user))
    if "platform.shop.merchant.list_all" in perms:
        return "all"
    if "platform.shop.merchant.list_assigned" in perms:
        return "assigned"
    if "platform.shop.analytics" in perms or "platform.shop.settlement" in perms:
        return "all"
    return resolve_merchant_list_scope(user)


def _assigned_tenant_ids(db: Session, user: User) -> list[UUID]:
    uid = str(user.id)
    uid_hex = user.id.hex
    return [
        tid
        for (tid,) in db.query(ShopMerchantAccount.tenant_id)
        .filter(
            or_(
                cast(ShopMerchantAccount.account_manager_user_id, String) == uid,
                cast(ShopMerchantAccount.account_manager_user_id, String) == uid_hex,
            )
        )
        .all()
    ]


def _tenant_clause(column, tenant_ids: list[UUID] | None):
    if tenant_ids is None:
        return None
    if not tenant_ids:
        return false()
    vals: list[str] = []
    for tid in tenant_ids:
        vals.append(str(tid))
        vals.append(tid.hex)
    return cast(column, String).in_(vals)


def _apply(q, column, tenant_ids: list[UUID] | None):
    clause = _tenant_clause(column, tenant_ids)
    if clause is not None:
        return q.filter(clause)
    return q


def _count(q) -> int:
    return int(q.scalar() or 0)


def _scope_tenants(db: Session, user: User, scope: str) -> list[UUID] | None:
    if scope == "assigned":
        return _assigned_tenant_ids(db, user)
    return None


def _gmv_and_orders(
    db: Session,
    tenant_ids: list[UUID] | None,
    start: datetime,
    end: datetime | None = None,
) -> tuple[int, int]:
    q = db.query(
        func.coalesce(func.sum(func.coalesce(ShopOrder.paid_amount_cents, ShopOrder.amount_cents)), 0),
        func.count(ShopOrder.id),
    ).filter(
        ShopOrder.paid_at.isnot(None),
        ShopOrder.paid_at >= start,
        ShopOrder.status.in_(_PAID_STATUSES),
    )
    if end is not None:
        q = q.filter(ShopOrder.paid_at < end)
    q = _apply(q, ShopOrder.tenant_id, tenant_ids)
    row = q.one()
    return int(row[0] or 0), int(row[1] or 0)


def _active_merchants(db: Session, tenant_ids: list[UUID] | None) -> int:
    q = db.query(func.count(ShopMerchantAccount.id)).filter(ShopMerchantAccount.status == "active")
    q = _apply(q, ShopMerchantAccount.tenant_id, tenant_ids)
    return _count(q)


def _widget_meta(*, cs: bool) -> dict:
    gmv_label = "所辖本月 GMV" if cs else "本月 GMV"
    active_label = "活跃客户" if cs else "活跃商家"
    return {
        "gmv_month_cents": {"label": gmv_label, "clickable": False, "format": "money"},
        "active_merchants": {"label": active_label, "clickable": False, "format": "number"},
        "pending_product_reviews": {
            "label": "待审商品",
            "clickable": True,
            "format": "number",
            "href": "/admin/shop/product-reviews?status=pending_review",
        },
        "pending_onboarding": {
            "label": "待审开通",
            "clickable": True,
            "format": "number",
            "href": "/admin/shop/onboarding?status=pending",
        },
        "open_moderation_cases": {
            "label": "违规待处理",
            "clickable": True,
            "format": "number",
            "href": "/admin/shop/moderation?view=open",
        },
        "pending_renewals": {
            "label": "待处理续费",
            "clickable": True,
            "format": "number",
            "href": "/admin/shop/subscriptions?todo=renewal",
        },
        "expiring_soon_merchants": {
            "label": "即将到期",
            "clickable": True,
            "format": "number",
            "href": "/admin/shop/merchants?tab=expiring_soon",
        },
        "my_pending_renewal_requests": {
            "label": "续费申请中",
            "clickable": True,
            "format": "number",
            "href": "/admin/shop/merchants?tab=my_clients",
        },
        "settlement_batches_pending": {
            "label": "待确认批次",
            "clickable": True,
            "format": "number",
            "href": "/admin/shop/settlements?status=pending",
        },
        "settlement_batches_failed": {
            "label": "打款失败",
            "clickable": True,
            "format": "number",
            "href": "/admin/shop/settlements?status=payment_failed",
        },
        "settled_month_cents": {
            "label": "本月已结算",
            "clickable": False,
            "format": "money",
        },
    }


def _title(role: str | None, assigned_count: int | None) -> dict:
    if role == PLATFORM_SHOP_ROLE_CS:
        return {
            "title": "我的客户经营看板",
            "subtitle": f"所辖 {assigned_count or 0} 家",
        }
    if role == PLATFORM_SHOP_ROLE_FINANCE:
        return {"title": "结算与经营概览", "subtitle": None}
    return {"title": "全站经营看板", "subtitle": None}


def _widget_order(role: str | None) -> list[str]:
    if role == PLATFORM_SHOP_ROLE_CS:
        return list(CS_ORDER)
    if role == PLATFORM_SHOP_ROLE_FINANCE:
        return list(FINANCE_ORDER)
    return list(OPS_ORDER)


def get_summary(db: Session, user: User) -> dict:
    perms = set(get_platform_shop_permissions(user))
    role = get_platform_shop_role(user)
    scope = resolve_analytics_scope(user)
    tenant_ids = _scope_tenants(db, user, scope)
    assigned_count = len(tenant_ids) if tenant_ids is not None else None
    month_start = _month_start()

    widgets: dict = {k: None for k in WIDGET_KEYS}

    if "platform.shop.analytics" in perms:
        gmv, _ = _gmv_and_orders(db, tenant_ids, month_start)
        widgets["gmv_month_cents"] = gmv
        widgets["active_merchants"] = _active_merchants(db, tenant_ids)

    if "platform.shop.product.review" in perms:
        q = db.query(func.count(ShopProduct.id)).filter(
            ShopProduct.status == "pending_review",
            ShopProduct.deleted_at.is_(None),
        )
        q = _apply(q, ShopProduct.tenant_id, tenant_ids)
        widgets["pending_product_reviews"] = _count(q)

    if perms.intersection(
        {
            "platform.shop.approve",
            "platform.shop.onboarding.initiate",
            "platform.shop.merchant.read",
        }
    ):
        q = db.query(func.count(ShopOnboardingApplication.id)).filter(
            ShopOnboardingApplication.status == "pending"
        )
        q = _apply(q, ShopOnboardingApplication.tenant_id, tenant_ids)
        widgets["pending_onboarding"] = _count(q)

    if "platform.shop.moderate" in perms:
        q = db.query(func.count(ShopModerationCase.id)).filter(
            ShopModerationCase.status.in_(("pending", "processing"))
        )
        q = _apply(q, ShopModerationCase.tenant_id, tenant_ids)
        widgets["open_moderation_cases"] = _count(q)

    if "platform.shop.subscription.manage" in perms:
        q = db.query(func.count(ShopMerchantServiceLog.id)).filter(
            ShopMerchantServiceLog.type == "renewal_request",
            ShopMerchantServiceLog.status.in_(("pending", "processing")),
        )
        q = _apply(q, ShopMerchantServiceLog.tenant_id, tenant_ids)
        widgets["pending_renewals"] = _count(q)

    cs_view = role == PLATFORM_SHOP_ROLE_CS or (
        scope == "assigned" and "platform.shop.merchant.read" in perms
    )
    if cs_view and "platform.shop.merchant.read" in perms:
        q = db.query(func.count(ShopMerchantAccount.id)).filter(
            ShopMerchantAccount.plan_status == "expiring_soon"
        )
        q = _apply(q, ShopMerchantAccount.tenant_id, tenant_ids)
        widgets["expiring_soon_merchants"] = _count(q)
        q = db.query(func.count(ShopMerchantServiceLog.id)).filter(
            ShopMerchantServiceLog.type == "renewal_request",
            ShopMerchantServiceLog.status.in_(("pending", "processing")),
        )
        q = _apply(q, ShopMerchantServiceLog.tenant_id, tenant_ids)
        widgets["my_pending_renewal_requests"] = _count(q)

    if "platform.shop.settlement" in perms:
        pending_q = db.query(func.count(ShopSettlementBatch.id)).filter(
            ShopSettlementBatch.status == "pending"
        )
        failed_q = db.query(func.count(ShopSettlementBatch.id)).filter(
            ShopSettlementBatch.status == "payment_failed"
        )
        pending_q = _apply(pending_q, ShopSettlementBatch.tenant_id, tenant_ids)
        failed_q = _apply(failed_q, ShopSettlementBatch.tenant_id, tenant_ids)
        widgets["settlement_batches_pending"] = _count(pending_q)
        widgets["settlement_batches_failed"] = _count(failed_q)

    if "platform.shop.settlement" in perms or "platform.shop.analytics" in perms:
        settled_q = db.query(
            func.coalesce(func.sum(ShopSettlementBatch.net_amount_cents), 0)
        ).filter(
            ShopSettlementBatch.paid_at.isnot(None),
            ShopSettlementBatch.paid_at >= month_start,
        )
        settled_q = _apply(settled_q, ShopSettlementBatch.tenant_id, tenant_ids)
        widgets["settled_month_cents"] = int(settled_q.scalar() or 0)

    finance_table = (
        role == PLATFORM_SHOP_ROLE_FINANCE
        or (
            "platform.shop.settlement" in perms
            and "platform.shop.merchant.read" not in perms
        )
    )
    if finance_table:
        merchant_table = _settlement_table(db, tenant_ids)
    else:
        merchant_table = _top_gmv_table(db, tenant_ids, month_start, cs=role == PLATFORM_SHOP_ROLE_CS)

    heading = _title(role, assigned_count)
    return {
        "scope": scope,
        "platform_shop_role": role,
        "title": heading["title"],
        "subtitle": heading["subtitle"],
        "assigned_merchant_count": assigned_count,
        "widget_order": _widget_order(role),
        "widget_meta": _widget_meta(cs=role == PLATFORM_SHOP_ROLE_CS),
        "widgets": widgets,
        "merchant_table": merchant_table,
        "gaps": {
            "p05_settlement_page": False,
            "p07_moderation_page": True,
        },
    }


def _top_gmv_table(
    db: Session,
    tenant_ids: list[UUID] | None,
    month_start: datetime,
    *,
    cs: bool,
    limit: int = 10,
) -> dict:
    gmv_q = (
        db.query(
            ShopOrder.tenant_id,
            func.coalesce(func.sum(func.coalesce(ShopOrder.paid_amount_cents, ShopOrder.amount_cents)), 0).label(
                "gmv"
            ),
            func.count(ShopOrder.id).label("order_count"),
            func.max(ShopOrder.paid_at).label("last_active_at"),
        )
        .filter(
            ShopOrder.paid_at.isnot(None),
            ShopOrder.paid_at >= month_start,
            ShopOrder.status.in_(_PAID_STATUSES),
        )
        .group_by(ShopOrder.tenant_id)
    )
    gmv_q = _apply(gmv_q, ShopOrder.tenant_id, tenant_ids)
    gmv_map = {row[0]: row for row in gmv_q.all()}

    mq = db.query(ShopMerchantAccount)
    mq = _apply(mq, ShopMerchantAccount.tenant_id, tenant_ids)
    merchants = mq.all()
    items = []
    for m in merchants:
        row = gmv_map.get(m.tenant_id)
        last_follow = None
        if cs:
            last_follow = (
                db.query(func.max(ShopMerchantServiceLog.created_at))
                .filter(
                    or_(
                        cast(ShopMerchantServiceLog.tenant_id, String) == str(m.tenant_id),
                        cast(ShopMerchantServiceLog.tenant_id, String) == m.tenant_id.hex,
                    )
                )
                .scalar()
            )
        items.append(
            {
                "tenant_id": str(m.tenant_id),
                "name": m.display_name or m.legal_name or "",
                "gmv_month_cents": int(row[1] if row else 0),
                "order_count": int(row[2] if row else 0),
                "onboarding_status": m.status,
                "plan_status": m.plan_status,
                "benefits_until": m.benefits_until.isoformat() if m.benefits_until else None,
                "last_active_at": (row[3].isoformat() if row and row[3] else None),
                "last_follow_up_at": last_follow.isoformat() if last_follow else None,
            }
        )
    items.sort(key=lambda x: x["gmv_month_cents"], reverse=True)
    return {
        "kind": "top_gmv_merchants",
        "scope": "assigned" if tenant_ids is not None else "all",
        "items": items[:limit],
    }


def _settlement_table(db: Session, tenant_ids: list[UUID] | None, limit: int = 10) -> dict:
    q = db.query(ShopSettlementBatch).order_by(ShopSettlementBatch.created_at.desc())
    q = _apply(q, ShopSettlementBatch.tenant_id, tenant_ids)
    rows = q.limit(limit).all()
    return {
        "kind": "recent_settlement_batches",
        "scope": "assigned" if tenant_ids is not None else "all",
        "items": [
            {
                "id": str(b.id),
                "batch_no": b.batch_no,
                "period_start": b.period_start.isoformat() if b.period_start else None,
                "period_end": b.period_end.isoformat() if b.period_end else None,
                "net_amount_cents": int(b.net_amount_cents or 0),
                "status": b.status,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in rows
        ],
    }


def get_trends(db: Session, user: User, range_key: str) -> dict:
    if range_key not in ("7d", "30d"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="range 仅支持 7d 或 30d")
    days = 7 if range_key == "7d" else 30
    scope = resolve_analytics_scope(user)
    tenant_ids = _scope_tenants(db, user, scope)
    today = _now().date()
    points = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        start, end = _day_range(day)
        gmv, orders = _gmv_and_orders(db, tenant_ids, start, end)
        points.append({"date": day.isoformat(), "gmv_cents": gmv, "order_count": orders})
    return {"range": range_key, "scope": scope, "points": points}


def export_daily_csv(db: Session, user: User, day: date) -> str:
    summary = get_summary(db, user)
    start, end = _day_range(day)
    tenant_ids = _scope_tenants(db, user, summary["scope"])
    gmv, orders = _gmv_and_orders(db, tenant_ids, start, end)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["日期", day.isoformat()])
    w.writerow(["范围", summary["scope"]])
    w.writerow(["标题", summary["title"]])
    w.writerow([])
    w.writerow(["指标", "数值"])
    w.writerow(["当日 GMV（分）", gmv])
    w.writerow(["当日订单", orders])
    meta = summary["widget_meta"]
    for key in summary["widget_order"]:
        val = summary["widgets"].get(key)
        if val is None:
            continue
        label = (meta.get(key) or {}).get("label") or key
        w.writerow([label, val])
    table = summary["merchant_table"]
    w.writerow([])
    if table.get("kind") == "recent_settlement_batches":
        w.writerow(["批次号", "周期起", "周期止", "净额（分）", "状态"])
        for it in table.get("items") or []:
            w.writerow(
                [
                    it.get("batch_no") or "",
                    it.get("period_start") or "",
                    it.get("period_end") or "",
                    it.get("net_amount_cents") or 0,
                    it.get("status") or "",
                ]
            )
    else:
        w.writerow(["商家", "本月 GMV（分）", "订单", "状态", "最近活跃"])
        for it in table.get("items") or []:
            w.writerow(
                [
                    it.get("name") or "",
                    it.get("gmv_month_cents") or 0,
                    it.get("order_count") or 0,
                    it.get("onboarding_status") or "",
                    it.get("last_active_at") or "",
                ]
            )
    return buf.getvalue()
