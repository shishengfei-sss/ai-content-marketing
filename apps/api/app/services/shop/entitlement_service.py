"""F8 权益合并与生效时间归一化。对照 PRD：03#f8 · 04#subscription-dates。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models.shop import ShopMerchantAccount, ShopMerchantSubscription, ShopPlanFeature, ShopSubscriptionPlan

try:
    from zoneinfo import ZoneInfo

    TZ_SH = ZoneInfo("Asia/Shanghai")
except Exception:  # Windows 无 tzdata 时回退固定东八区
    TZ_SH = timezone(timedelta(hours=8))
UNLIMITED = "unlimited"


def date_to_effective_at(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=TZ_SH)


def date_to_expires_at_exclusive(d: date) -> datetime:
    """止日 inclusive → 库内 exclusive 上界（止日次日 00:00）。"""
    return datetime.combine(d + timedelta(days=1), time.min, tzinfo=TZ_SH)


def exclusive_to_inclusive_date(dt: datetime) -> date:
    local = dt.astimezone(TZ_SH)
    return local.date() - timedelta(days=1)


def now_sh() -> datetime:
    return datetime.now(TZ_SH)


def is_subscription_active(sub: ShopMerchantSubscription, at: datetime | None = None) -> bool:
    at = at or now_sh()
    if sub.status != "active":
        return False
    eff = sub.effective_at
    exp = sub.expires_at
    if eff.tzinfo is None:
        eff = eff.replace(tzinfo=timezone.utc).astimezone(TZ_SH)
    else:
        eff = eff.astimezone(TZ_SH)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc).astimezone(TZ_SH)
    else:
        exp = exp.astimezone(TZ_SH)
    return eff <= at < exp


def _mode_for_code(db: Session, code: str, cache: dict[str, ShopPlanFeature]) -> str:
    if code not in cache:
        cache[code] = db.query(ShopPlanFeature).filter(ShopPlanFeature.code == code).first()
    feat = cache.get(code)
    if feat and feat.aggregate_mode:
        return feat.aggregate_mode
    if code.startswith("channel.") or code.startswith("feature."):
        return "any"
    if code == "quota.max_shops":
        return "max"
    return "sum"


def merge_entitlements(db: Session, snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    """按功能字典 aggregate_mode 合并多条 plan_snapshot。"""
    cache: dict[str, ShopPlanFeature] = {}
    quotas: dict[str, Any] = {}
    features: dict[str, Any] = {}
    usage_limits: dict[str, Any] = {}

    def merge_num(bag: dict[str, Any], code: str, val: Any, mode: str) -> None:
        if val == UNLIMITED:
            bag[code] = UNLIMITED
            return
        if bag.get(code) == UNLIMITED:
            return
        cur = bag.get(code)
        if cur is None:
            bag[code] = val
            return
        if mode == "max":
            bag[code] = max(int(cur), int(val))
        else:  # sum
            bag[code] = int(cur) + int(val)

    for snap in snapshots:
        for code, val in (snap.get("quotas") or {}).items():
            merge_num(quotas, code, val, _mode_for_code(db, code, cache))
        for code, val in (snap.get("usage_limits") or {}).items():
            merge_num(usage_limits, code, val, _mode_for_code(db, code, cache))
        for code, val in (snap.get("features") or {}).items():
            if val is True or val == UNLIMITED:
                features[code] = True
            elif code not in features:
                features[code] = bool(val)

    return {
        "quotas": quotas,
        "features": features,
        "usage_limits": usage_limits,
    }


def free_plan_snapshot(db: Session) -> dict[str, Any] | None:
    plan = db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.code == "free").first()
    if not plan:
        return None
    return build_plan_snapshot(plan)


def build_plan_snapshot(plan: ShopSubscriptionPlan) -> dict[str, Any]:
    return {
        "plan_id": str(plan.id),
        "plan_code": plan.code,
        "plan_name": plan.name,
        "plan_type": plan.plan_type,
        "replace_group": plan.replace_group,
        "stackable": plan.stackable,
        "billing_period": plan.billing_period,
        "quotas": dict(plan.quotas or {}),
        "features": dict(plan.features or {}),
        "usage_limits": dict(plan.usage_limits or {}),
    }


def list_active_subscriptions(db: Session, tenant_id: UUID) -> list[ShopMerchantSubscription]:
    rows = (
        db.query(ShopMerchantSubscription)
        .filter(
            uuid_eq(ShopMerchantSubscription.tenant_id, tenant_id),
            ShopMerchantSubscription.status == "active",
        )
        .all()
    )
    return [r for r in rows if is_subscription_active(r)]


def _fmt_entitlement_val(val: Any) -> str:
    return "∞" if val == UNLIMITED else str(val)


def _feature_display_name(feat: ShopPlanFeature | None, code: str) -> str:
    name = feat.name if feat and feat.name else code
    if feat and feat.usage_period == "monthly":
        return f"{name} / 月"
    return name


def format_preview_lines(
    db: Session,
    current: dict[str, Any],
    incoming: dict[str, Any],
    merged: dict[str, Any],
) -> list[str]:
    """对照 #p11a-stack / #p11b：展示名字典原文，如「领权短信 / 月：500+500=1000（累加）」。"""
    cache: dict[str, ShopPlanFeature] = {}
    mode_zh = {"sum": "累加", "max": "取最大值", "any": "任一满足"}
    lines: list[str] = []

    def feat_of(code: str) -> ShopPlanFeature | None:
        if code not in cache:
            cache[code] = db.query(ShopPlanFeature).filter(ShopPlanFeature.code == code).first()
        return cache.get(code)

    for bag in ("quotas", "usage_limits"):
        for code, new_val in (incoming.get(bag) or {}).items():
            feat = feat_of(code)
            label = _feature_display_name(feat, code)
            mode = _mode_for_code(db, code, cache)
            old = (current.get(bag) or {}).get(code)
            result = (merged.get(bag) or {}).get(code, new_val)
            zh = mode_zh.get(mode, mode)
            if (
                mode == "sum"
                and old is not None
                and old != UNLIMITED
                and new_val != UNLIMITED
                and result != UNLIMITED
            ):
                lines.append(
                    f"{label}：{_fmt_entitlement_val(old)}+{_fmt_entitlement_val(new_val)}"
                    f"={_fmt_entitlement_val(result)}（{zh}）"
                )
            else:
                lines.append(f"{label}：{_fmt_entitlement_val(result)}（{zh}）")
    for code, val in (incoming.get("features") or {}).items():
        if val is True or val == UNLIMITED:
            feat = feat_of(code)
            lines.append(f"{_feature_display_name(feat, code)}：开")
    return lines


def preview_merged_entitlements(
    db: Session,
    tenant_id: UUID,
    preview_plan: str,
    preview_mode: str | None = None,
) -> dict[str, Any]:
    """模拟 stack / replace 后 merge。对照 #p11a-stack C15 · #p11b C16。"""
    code = (preview_plan or "").strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请选择预览套餐")
    plan = db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.code == code).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="套餐不存在")
    mode = (preview_mode or "").strip() or ("stack" if plan.plan_type == "addon" else "replace")
    if mode not in ("stack", "replace"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="预览方式无效")

    incoming = build_plan_snapshot(plan)
    active = list_active_subscriptions(db, tenant_id)
    current_snaps = [dict(s.plan_snapshot or {}) for s in active]
    if not current_snaps:
        free = free_plan_snapshot(db)
        if free:
            current_snaps = [free]
    if mode == "replace":
        snapshots = []
        for s in active:
            snap = dict(s.plan_snapshot or {})
            is_main = snap.get("plan_type") == "main" or s.purchase_mode == "replace"
            if is_main:
                continue
            snapshots.append(snap)
        snapshots.append(incoming)
    else:
        snapshots = list(current_snaps)
        snapshots.append(incoming)

    current = merge_entitlements(db, current_snaps)
    merged = merge_entitlements(db, snapshots)
    lines = format_preview_lines(db, current, incoming, merged)
    return {
        "tenant_id": str(tenant_id),
        "preview_plan": plan.code,
        "preview_plan_name": plan.name,
        "preview_mode": mode,
        "preview_lines": lines,
        "preview_text": " · ".join(lines) if lines else "无变化",
        "active_subscription_ids": [str(s.id) for s in active],
        "contributing_plans": [
            {
                "plan_code": snap.get("plan_code"),
                "plan_name": snap.get("plan_name"),
                "plan_type": snap.get("plan_type"),
            }
            for snap in snapshots
        ],
        **merged,
    }


def get_merged_entitlements(db: Session, tenant_id: UUID) -> dict[str, Any]:
    active = list_active_subscriptions(db, tenant_id)
    snapshots = [dict(s.plan_snapshot or {}) for s in active]
    if not snapshots:
        free = free_plan_snapshot(db)
        if free:
            snapshots = [free]
    merged = merge_entitlements(db, snapshots)
    return {
        "tenant_id": str(tenant_id),
        "active_subscription_ids": [str(s.id) for s in active],
        "contributing_plans": [
            {
                "subscription_id": str(s.id),
                "subscription_no": s.subscription_no,
                "plan_code": (s.plan_snapshot or {}).get("plan_code"),
                "plan_name": (s.plan_snapshot or {}).get("plan_name"),
                "plan_type": (s.plan_snapshot or {}).get("plan_type"),
                "purchase_mode": s.purchase_mode,
                "expires_at_inclusive": exclusive_to_inclusive_date(s.expires_at).isoformat(),
            }
            for s in active
        ],
        **merged,
    }


def refresh_merchant_plan_fields(db: Session, merchant: ShopMerchantAccount) -> None:
    active = list_active_subscriptions(db, merchant.tenant_id)
    mains = [
        s
        for s in active
        if (s.plan_snapshot or {}).get("plan_type") == "main"
        or s.purchase_mode == "replace"
    ]
    # 主套餐：prefer replace_group main / plan_type main
    main = None
    for s in mains:
        if (s.plan_snapshot or {}).get("plan_type") == "main":
            main = s
            break
    if main is None and active:
        main = max(active, key=lambda x: x.expires_at)

    if main:
        merchant.current_subscription_id = main.id
        merchant.plan_label = (main.plan_snapshot or {}).get("plan_name") or merchant.plan_label
        inclusive = exclusive_to_inclusive_date(main.expires_at)
        merchant.benefits_until = inclusive
        days_left = (inclusive - now_sh().date()).days
        if days_left < 0:
            merchant.plan_status = "expired"
        elif days_left <= 30:
            merchant.plan_status = "expiring_soon"
        else:
            merchant.plan_status = "active"
    elif active:
        # 仅加购仍有效
        latest = max(active, key=lambda x: x.expires_at)
        merchant.current_subscription_id = latest.id
        merchant.plan_label = (latest.plan_snapshot or {}).get("plan_name")
        merchant.benefits_until = exclusive_to_inclusive_date(latest.expires_at)
        merchant.plan_status = "active"
    else:
        # 全部到期：回落免费版展示
        hist = (
            db.query(ShopMerchantSubscription)
            .filter(uuid_eq(ShopMerchantSubscription.tenant_id, merchant.tenant_id))
            .order_by(ShopMerchantSubscription.expires_at.desc())
            .first()
        )
        if hist:
            merchant.plan_label = f"免费版（已到期）"
            merchant.plan_status = "expired"
            merchant.benefits_until = exclusive_to_inclusive_date(hist.expires_at)
        else:
            merchant.plan_label = "免费版"
            merchant.plan_status = "active"
            merchant.benefits_until = None
        merchant.current_subscription_id = None

    merged = get_merged_entitlements(db, merchant.tenant_id)
    shops = (merged.get("quotas") or {}).get("quota.max_shops")
    if shops == UNLIMITED:
        merchant.store_quota = None
    elif isinstance(shops, int):
        merchant.store_quota = shops


def assert_merchant_writable_by_plan(db: Session, tenant_id: UUID) -> None:
    """到期后写交易类 API 守卫（VS-M1-08）。"""
    merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    )
    if not merchant:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="商家不存在")
    active = list_active_subscriptions(db, tenant_id)
    if not active and merchant.plan_status == "expired":
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="套餐已到期")
