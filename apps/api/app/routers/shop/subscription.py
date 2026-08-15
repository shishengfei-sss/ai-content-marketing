"""A18 商家端套餐权益只读。对照 PRD：01#a18 · §8.6。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db, uuid_eq
from app.dependencies import TenantContext
from app.models.shop import ShopMerchantAccount
from app.services.permission_service import require_permission
from app.services.shop import a18_service

router = APIRouter(prefix="/subscription", tags=["shop-subscription"])


@router.get("/overview")
def subscription_overview(
    ctx: TenantContext = Depends(require_permission("shop.subscription.usage.read")),
    db: Session = Depends(get_db),
):
    """A18 套餐信息整页数据。"""
    return a18_service.get_a18_overview(db, ctx.tenant_id)


@router.get("/usage")
def subscription_usage(
    ctx: TenantContext = Depends(require_permission("shop.subscription.usage.read")),
    db: Session = Depends(get_db),
):
    """合并用量：used / merged_limit。"""
    return a18_service.get_usage_payload(db, ctx.tenant_id)


@router.get("/entitlements")
def my_entitlements(
    ctx: TenantContext = Depends(require_permission("shop.subscription.usage.read")),
    db: Session = Depends(get_db),
):
    merchant = (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, ctx.tenant_id))
        .first()
    )
    if not merchant:
        return {"state": "not_onboarded", "quotas": {}, "features": {}, "usage_limits": {}}
    overview = a18_service.get_a18_overview(db, merchant.tenant_id)
    merged = overview.get("merged") or {}
    return {
        "state": "onboarded",
        "merchant_id": str(merchant.id),
        "plan_label": overview.get("plan_label"),
        "plan_status": overview.get("plan_status"),
        "benefits_until": overview.get("benefits_until"),
        "quotas": merged.get("quotas") or {},
        "features": merged.get("features") or {},
        "usage_limits": merged.get("usage_limits") or {},
        "contributing_plans": merged.get("contributing_plans") or [],
        "active_subscription_ids": merged.get("active_subscription_ids") or [],
        "usage_groups": overview.get("usage_groups") or [],
        "summary": overview.get("summary"),
    }


@router.get("/subscriptions")
def my_subscriptions(
    ctx: TenantContext = Depends(require_permission("shop.subscription.usage.read")),
    db: Session = Depends(get_db),
):
    return {"items": a18_service.list_subscriptions_for_a18(db, ctx.tenant_id)}
