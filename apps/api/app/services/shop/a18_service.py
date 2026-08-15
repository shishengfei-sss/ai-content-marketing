"""A18 商家端套餐信息：合并权益 + 用量。对照 #a18 · PRD §8.6。"""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models.shop import (
    ShopMerchantAccount,
    ShopMerchantSubscription,
    ShopProduct,
    ShopProductReview,
    ShopSmsLog,
    ShopStore,
)
from app.services.shop.entitlement_service import (
    UNLIMITED,
    exclusive_to_inclusive_date,
    get_merged_entitlements,
    is_subscription_active,
    list_active_subscriptions,
    now_sh,
    refresh_merchant_plan_fields,
)
# 展示名 / 去哪用（商家文案，禁止内部代号）
LEAF_META: dict[str, dict[str, str]] = {
    "quota.max_shops": {
        "label": "店铺数",
        "group": "店铺与商品",
        "hint": "含草稿+暂停计入",
        "link_path": "/shop/stores",
        "link_label": "店铺管理",
        "period_label": "",
    },
    "quota.max_products": {
        "label": "在售商品槽位",
        "group": "店铺与商品",
        "hint": "仅统计在售商品",
        "link_path": "/shop/products",
        "link_label": "商品管理",
        "period_label": "",
    },
    "usage.product_review_submit": {
        "label": "商品提审（今日）",
        "group": "店铺与商品",
        "hint": "每日 0 点重置",
        "link_path": "/shop/products",
        "link_label": "提交审核",
        "period_label": "今日",
    },
    "usage.sms_claim_send": {
        "label": "领权短信（本月）",
        "group": "营销触达",
        "hint": "发送占用额度",
        "link_path": "/shop/sms-settings",
        "link_label": "短信领权",
        "period_label": "本月",
    },
    "channel.doudian": {
        "label": "抖店公域回流",
        "group": "公域与增值",
        "hint": "",
        "link_path": "/shop/channel-mappings",
        "link_label": "公域映射",
        "period_label": "",
    },
    "feature.invoice": {
        "label": "买家开票",
        "group": "公域与增值",
        "hint": "",
        "link_path": "/shop/invoices",
        "link_label": "开票",
        "period_label": "",
    },
}

GROUP_ORDER = ["店铺与商品", "营销触达", "公域与增值"]


def _day_bounds_utc() -> tuple[datetime, datetime]:
    local = now_sh()
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local.replace(hour=23, minute=59, second=59)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _month_bounds_utc() -> tuple[datetime, datetime]:
    local = now_sh()
    start_local = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last = monthrange(local.year, local.month)[1]
    end_local = local.replace(day=last, hour=23, minute=59, second=59)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def count_shops_used(db: Session, tenant_id: UUID) -> int:
    return (
        db.query(func.count(ShopStore.id))
        .filter(uuid_eq(ShopStore.tenant_id, tenant_id), ShopStore.status != "closed")
        .scalar()
        or 0
    )


def count_on_sale_products(db: Session, tenant_id: UUID) -> int:
    return (
        db.query(func.count(ShopProduct.id))
        .filter(
            uuid_eq(ShopProduct.tenant_id, tenant_id),
            ShopProduct.status == "on_sale",
            ShopProduct.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )


def count_today_review_submits(db: Session, tenant_id: UUID) -> int:
    start, end = _day_bounds_utc()
    return (
        db.query(func.count(ShopProductReview.id))
        .filter(
            uuid_eq(ShopProductReview.tenant_id, tenant_id),
            ShopProductReview.submitted_at >= start,
            ShopProductReview.submitted_at <= end,
        )
        .scalar()
        or 0
    )


def count_month_sms(db: Session, tenant_id: UUID) -> int:
    start, end = _month_bounds_utc()
    return (
        db.query(func.count(ShopSmsLog.id))
        .filter(
            uuid_eq(ShopSmsLog.tenant_id, tenant_id),
            ShopSmsLog.created_at >= start,
            ShopSmsLog.created_at <= end,
        )
        .scalar()
        or 0
    )


def _limit_display(val: Any) -> str | int | None:
    if val == UNLIMITED or val == "unlimited":
        return "不限"
    if val is None:
        return None
    return val


def _pct(used: int, limit: Any) -> float | None:
    if limit == UNLIMITED or limit == "unlimited" or limit is None:
        return None
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        return None
    if lim <= 0:
        return 100.0
    return min(100.0, round(100.0 * used / lim, 1))


def _over(used: int, limit: Any) -> bool:
    if limit == UNLIMITED or limit == "unlimited" or limit is None:
        return False
    try:
        return used > int(limit)
    except (TypeError, ValueError):
        return False


def _at_limit(used: int, limit: Any) -> bool:
    if limit == UNLIMITED or limit == "unlimited" or limit is None:
        return False
    try:
        return used >= int(limit)
    except (TypeError, ValueError):
        return False


def build_usage_items(db: Session, tenant_id: UUID, merged: dict[str, Any]) -> list[dict]:
    quotas = merged.get("quotas") or {}
    usage_limits = merged.get("usage_limits") or {}
    features = merged.get("features") or {}

    shops_used = count_shops_used(db, tenant_id)
    products_used = count_on_sale_products(db, tenant_id)
    reviews_used = count_today_review_submits(db, tenant_id)
    sms_used = count_month_sms(db, tenant_id)

    items: list[dict] = []

    def add_meter(code: str, used: int, limit: Any, kind: str = "meter") -> None:
        meta = LEAF_META.get(code, {"label": code, "group": "其他", "hint": "", "link_path": "", "link_label": ""})
        items.append(
            {
                "code": code,
                "kind": kind,
                "label": meta["label"],
                "group": meta["group"],
                "hint": meta.get("hint") or "",
                "period_label": meta.get("period_label") or "",
                "used": used,
                "limit": limit if limit != UNLIMITED else "unlimited",
                "limit_label": _limit_display(limit),
                "percent": _pct(used, limit),
                "over_limit": _over(used, limit),
                "at_limit": _at_limit(used, limit),
                "link_path": meta.get("link_path") or "",
                "link_label": meta.get("link_label") or "",
                "enabled": None,
            }
        )

    def add_feature(code: str, enabled: bool) -> None:
        meta = LEAF_META.get(code, {"label": code, "group": "公域与增值", "hint": "", "link_path": "", "link_label": ""})
        items.append(
            {
                "code": code,
                "kind": "feature",
                "label": meta["label"],
                "group": meta["group"],
                "hint": meta.get("hint") or "",
                "period_label": "",
                "used": None,
                "limit": None,
                "limit_label": None,
                "percent": None,
                "over_limit": False,
                "at_limit": False,
                "link_path": meta.get("link_path") or "",
                "link_label": meta.get("link_label") or "",
                "enabled": bool(enabled),
            }
        )

    add_meter("quota.max_shops", shops_used, quotas.get("quota.max_shops", 1))
    add_meter("quota.max_products", products_used, quotas.get("quota.max_products", 20))
    add_meter(
        "usage.product_review_submit",
        reviews_used,
        usage_limits.get("usage.product_review_submit", 3),
    )
    # 短信：无上限时仍展示已用
    sms_limit = usage_limits.get("usage.sms_claim_send")
    if sms_limit is None and "usage.sms_claim_send" not in usage_limits:
        # 字典有、套餐可能未配 → 展示为未配置上限
        sms_limit = None
    add_meter("usage.sms_claim_send", sms_used, sms_limit if sms_limit is not None else "unlimited")

    add_feature("channel.doudian", bool(features.get("channel.doudian")))
    add_feature("feature.invoice", bool(features.get("feature.invoice")))
    return items


def group_usage_items(items: list[dict]) -> list[dict]:
    by: dict[str, list] = {}
    for it in items:
        by.setdefault(it["group"], []).append(it)
    groups = []
    for name in GROUP_ORDER:
        if name in by:
            groups.append({"group": name, "items": by.pop(name)})
    for name, vals in by.items():
        groups.append({"group": name, "items": vals})
    return groups


def list_subscriptions_for_a18(db: Session, tenant_id: UUID) -> list[dict]:
    from app.services.shop.entitlement_service import TZ_SH

    rows = (
        db.query(ShopMerchantSubscription)
        .filter(uuid_eq(ShopMerchantSubscription.tenant_id, tenant_id))
        .order_by(ShopMerchantSubscription.expires_at.desc())
        .limit(20)
        .all()
    )
    out = []
    for s in rows:
        active = is_subscription_active(s)
        snap = s.plan_snapshot or {}
        plan_type = snap.get("plan_type") or "main"
        eff = s.effective_at.astimezone(TZ_SH).date().isoformat() if s.effective_at else None
        exp = exclusive_to_inclusive_date(s.expires_at).isoformat() if s.expires_at else None
        out.append(
            {
                "id": s.id,
                "subscription_no": s.subscription_no,
                "plan_name": snap.get("plan_name") or "—",
                "plan_code": snap.get("plan_code"),
                "plan_type": plan_type,
                "plan_type_label": "主套餐" if plan_type == "main" else "叠加",
                "effective_at": eff,
                "expires_at_inclusive": exp,
                "status": "active" if active else "expired",
                "status_label": "生效中" if active else "已过期",
            }
        )
    return out


def get_a18_overview(db: Session, tenant_id: UUID) -> dict:
    merchant = (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id))
        .first()
    )
    if not merchant:
        return {"state": "not_onboarded"}

    refresh_merchant_plan_fields(db, merchant)
    db.flush()
    merged = get_merged_entitlements(db, tenant_id)
    active = list_active_subscriptions(db, tenant_id)
    usage_items = build_usage_items(db, tenant_id, merged)
    groups = group_usage_items(usage_items)

    shops_item = next((i for i in usage_items if i["code"] == "quota.max_shops"), None)
    alerts = []
    if shops_item and shops_item.get("over_limit"):
        alerts.append(
            {
                "level": "warning",
                "title": "店铺数已超限",
                "detail": f"{shops_item['used']} / {shops_item['limit_label']} · 请升级或清理草稿店",
            }
        )
    elif shops_item and shops_item.get("at_limit"):
        alerts.append(
            {
                "level": "warning",
                "title": "店铺数已达上限",
                "detail": f"{shops_item['used']} / {shops_item['limit_label']} · 新建店铺将禁用",
            }
        )

    mains = [s for s in active if (s.plan_snapshot or {}).get("plan_type") == "main"]
    addons = [s for s in active if (s.plan_snapshot or {}).get("plan_type") == "addon"]
    main_name = merchant.plan_label or (mains[0].plan_snapshot or {}).get("plan_name") if mains else "免费版"

    return {
        "state": "onboarded",
        "merchant_id": str(merchant.id),
        "plan_label": merchant.plan_label,
        "plan_status": merchant.plan_status,
        "benefits_until": merchant.benefits_until.isoformat() if merchant.benefits_until else None,
        "summary": {
            "main_plan_name": main_name,
            "benefits_until": merchant.benefits_until.isoformat() if merchant.benefits_until else None,
            "active_count": len(active),
            "addon_count": len(addons),
            "alerts": alerts,
        },
        "subscriptions": list_subscriptions_for_a18(db, tenant_id),
        "usage_groups": groups,
        "usage_items": usage_items,
        "merged": {
            "quotas": merged.get("quotas") or {},
            "features": merged.get("features") or {},
            "usage_limits": merged.get("usage_limits") or {},
            "contributing_plans": merged.get("contributing_plans") or [],
            "active_subscription_ids": merged.get("active_subscription_ids") or [],
        },
        "upgrade_hint": "Phase 1 请联系平台运营申请升级 / 加购（P11 人工开通）。",
    }


def get_usage_payload(db: Session, tenant_id: UUID) -> dict:
    """GET /shop/subscription/usage"""
    overview = get_a18_overview(db, tenant_id)
    if overview.get("state") == "not_onboarded":
        return {"state": "not_onboarded", "items": [], "groups": []}
    return {
        "state": "onboarded",
        "items": overview["usage_items"],
        "groups": overview["usage_groups"],
        "contributing_plans": overview["merged"]["contributing_plans"],
        "plan_label": overview.get("plan_label"),
        "benefits_until": overview.get("benefits_until"),
    }


# 平台端 P02-B 当前权益展示名（#p02b-entitlements 原文；与 A18 商家文案可不同）
P02B_LEAF_NAME: dict[str, str] = {
    "quota.max_shops": "店铺数",
    "quota.max_products": "在售商品上限",
    "usage.product_review_submit": "每日商品提审",
    "usage.sms_claim_send": "领权短信 / 月",
    "channel.doudian": "抖店公域",
    "feature.invoice": "电子发票",
}
MODE_ZH = {"max": "取最大", "sum": "累加", "any": "任一满足"}


def _source_for_code(snapshots: list[dict], code: str) -> str:
    names: list[str] = []
    for snap in snapshots:
        bags = (
            snap.get("quotas") or {},
            snap.get("usage_limits") or {},
            snap.get("features") or {},
        )
        if any(code in b for b in bags):
            name = snap.get("plan_name")
            if name and name not in names:
                names.append(name)
    return " + ".join(names) if names else "—"


def build_p02b_usage_payload(
    db: Session, tenant_id: UUID, merged: dict[str, Any] | None = None
) -> dict:
    """P02-B 合并权益树：计量与 A18 同源，分组名对齐线框。"""
    from app.services.shop.entitlement_service import _mode_for_code, free_plan_snapshot

    if merged is None:
        merged = get_merged_entitlements(db, tenant_id)
    items = build_usage_items(db, tenant_id, merged)
    active = list_active_subscriptions(db, tenant_id)
    snapshots = [dict(s.plan_snapshot or {}) for s in active]
    if not snapshots:
        free = free_plan_snapshot(db)
        if free:
            snapshots = [free]
    cache: dict[str, Any] = {}
    for it in items:
        mode = _mode_for_code(db, it["code"], cache)
        it["name"] = P02B_LEAF_NAME.get(it["code"], it["label"])
        it["aggregate_mode"] = mode
        it["aggregate_mode_label"] = MODE_ZH.get(mode, mode)
        if it.get("kind") == "feature":
            it["value_display"] = "✓" if it.get("enabled") else "—"
            it["used_display"] = "—"
        else:
            it["value_display"] = it.get("limit_label")
            used = it.get("used")
            it["used_display"] = "—" if used is None else used
        it["source"] = _source_for_code(snapshots, it["code"])
    return {"usage_items": items, "usage_groups": group_usage_items(items)}
