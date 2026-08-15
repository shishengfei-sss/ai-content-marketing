"""A19 单店设置。对照 PRD 01-管理端UI.html #a19。"""

from __future__ import annotations

import re
import uuid
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.shop import ShopMerchantAccount, ShopStore, ShopStoreSettings
from app.services.shop import category_service
from app.services.shop.product_service import ensure_default_shop

REFUND_POLICIES = frozenset({"always_allow", "before_fulfill", "manual_only"})
REFUND_LABELS = {
    "always_allow": "随时可退",
    "before_fulfill": "履约前可退",
    "manual_only": "仅人工审核",
}
THEME_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _merchant(db: Session, tenant_id: UUID) -> ShopMerchantAccount:
    m = (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id))
        .first()
    )
    if not m:
        raise HTTPException(status_code=404, detail="商家未开通商城")
    return m


def resolve_shop(db: Session, ctx: TenantContext, shop_id: UUID | None = None) -> ShopStore:
    merchant = _merchant(db, ctx.tenant_id)
    if shop_id:
        shop = (
            db.query(ShopStore)
            .filter(uuid_eq(ShopStore.id, shop_id), uuid_eq(ShopStore.tenant_id, ctx.tenant_id))
            .first()
        )
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
        return shop
    return ensure_default_shop(db, ctx.tenant_id, merchant)


def ensure_settings(db: Session, shop: ShopStore) -> ShopStoreSettings:
    row = (
        db.query(ShopStoreSettings)
        .filter(uuid_eq(ShopStoreSettings.shop_id, shop.id))
        .first()
    )
    if row:
        return row
    row = ShopStoreSettings(
        id=uuid.uuid4(),
        tenant_id=shop.tenant_id,
        shop_id=shop.id,
        intro=None,
        service_phone=None,
        theme_color="#1677ff",
        close_order_minutes=30,
        default_refund_policy="before_fulfill",
    )
    db.add(row)
    db.flush()
    return row


def get_default_refund_policy(db: Session, shop_id: UUID) -> str:
    row = (
        db.query(ShopStoreSettings)
        .filter(uuid_eq(ShopStoreSettings.shop_id, shop_id))
        .first()
    )
    if row and row.default_refund_policy in REFUND_POLICIES:
        return row.default_refund_policy
    return "before_fulfill"


def _out(shop: ShopStore, settings: ShopStoreSettings, *, category_name: str | None = None) -> dict:
    return {
        "shop_id": shop.id,
        "tenant_id": shop.tenant_id,
        "name": shop.name or "",
        "slug": shop.slug or "",
        "logo_url": shop.logo_url,
        "status": shop.status,
        "default_category_id": shop.default_category_id,
        "default_category_name": category_name,
        "allow_cross_shop_redeem": bool(shop.allow_cross_shop_redeem),
        "intro": settings.intro,
        "service_phone": settings.service_phone,
        "theme_color": settings.theme_color or "#1677ff",
        "close_order_minutes": int(settings.close_order_minutes or 30),
        "default_refund_policy": settings.default_refund_policy or "before_fulfill",
        "default_refund_policy_label": REFUND_LABELS.get(
            settings.default_refund_policy or "before_fulfill", ""
        ),
        "updated_at": settings.updated_at or shop.updated_at,
    }


def get_settings(db: Session, ctx: TenantContext, shop_id: UUID | None = None) -> dict:
    shop = resolve_shop(db, ctx, shop_id)
    settings = ensure_settings(db, shop)
    db.commit()
    cat_name = None
    if shop.default_category_id:
        try:
            cat = category_service.get_enabled_category(db, shop.default_category_id)
            cat_name = cat.name
        except HTTPException:
            # 可能已禁入，仍展示 id
            from app.models.shop import ShopPlatformCategory

            c = (
                db.query(ShopPlatformCategory)
                .filter(uuid_eq(ShopPlatformCategory.id, shop.default_category_id))
                .first()
            )
            cat_name = c.name if c else None
    return _out(shop, settings, category_name=cat_name)


def patch_display(
    db: Session,
    ctx: TenantContext,
    *,
    shop_id: UUID | None = None,
    name: str | None = None,
    logo_url: str | None = None,
    intro: str | None = None,
    service_phone: str | None = None,
    theme_color: str | None = None,
    close_order_minutes: int | None = None,
    default_category_id: UUID | None = None,
    clear_default_category: bool = False,
) -> dict:
    shop = resolve_shop(db, ctx, shop_id)
    settings = ensure_settings(db, shop)
    if name is not None:
        text = name.strip()
        if not text:
            raise HTTPException(status_code=422, detail="请填写店铺名称（对外）")
        if len(text) > 100:
            raise HTTPException(status_code=422, detail="店铺名称最多 100 字")
        shop.name = text
    if logo_url is not None:
        shop.logo_url = logo_url.strip() or None
    if intro is not None:
        settings.intro = intro.strip() or None
    if service_phone is not None:
        settings.service_phone = service_phone.strip() or None
    if theme_color is not None:
        color = theme_color.strip()
        if color and not THEME_RE.match(color):
            raise HTTPException(status_code=422, detail="主题色须为 #RRGGBB")
        settings.theme_color = color or "#1677ff"
    if close_order_minutes is not None:
        mins = int(close_order_minutes)
        if mins < 5 or mins > 1440:
            raise HTTPException(status_code=422, detail="未支付关单须在 5–1440 分钟")
        settings.close_order_minutes = mins
    if clear_default_category:
        shop.default_category_id = None
    elif default_category_id is not None:
        category_service.get_enabled_category(db, default_category_id)
        shop.default_category_id = default_category_id
    db.commit()
    return get_settings(db, ctx, shop.id)


def patch_refund_default(
    db: Session,
    ctx: TenantContext,
    *,
    shop_id: UUID | None = None,
    default_refund_policy: str,
) -> dict:
    if default_refund_policy not in REFUND_POLICIES:
        raise HTTPException(status_code=422, detail="退款默认策略无效")
    shop = resolve_shop(db, ctx, shop_id)
    settings = ensure_settings(db, shop)
    settings.default_refund_policy = default_refund_policy
    db.commit()
    return get_settings(db, ctx, shop.id)


def list_stores(db: Session, ctx: TenantContext) -> list[dict]:
    rows = (
        db.query(ShopStore)
        .filter(uuid_eq(ShopStore.tenant_id, ctx.tenant_id), ShopStore.status != "closed")
        .order_by(ShopStore.created_at.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "slug": r.slug,
            "status": r.status,
            "logo_url": r.logo_url,
            "default_category_id": r.default_category_id,
        }
        for r in rows
    ]
