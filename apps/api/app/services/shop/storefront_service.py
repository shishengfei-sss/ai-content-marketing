"""买家店首页 / 商品详情（M02 / M03）。对照 PRD §8.12.2。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models.shop import (
    ShopBuyer,
    ShopEntitlement,
    ShopMerchantAccount,
    ShopProduct,
    ShopStore,
    ShopStoreSettings,
)
from app.schemas.shop_platform import (
    MpProductDetailOut,
    MpProductLessonPreview,
    MpStoreBriefOut,
    MpStoreProductCard,
    MpStorefrontResponse,
)
from app.services.shop import content_cms_service
from app.services.shop.content_fulfillment_service import _default_lessons


def _merchant_for_store(db: Session, shop: ShopStore) -> ShopMerchantAccount | None:
    if shop.merchant_id:
        return (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.id, shop.merchant_id))
            .first()
        )
    return (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, shop.tenant_id))
        .first()
    )


def _assert_trade_open(shop: ShopStore, merchant: ShopMerchantAccount | None) -> None:
    if merchant is None or merchant.status != "active":
        raise HTTPException(status_code=403, detail="店铺暂停营业")
    if shop.status != "active":
        raise HTTPException(status_code=403, detail="店铺暂停营业")


def _get_store(db: Session, shop_id: UUID) -> tuple[ShopStore, ShopMerchantAccount | None]:
    shop = db.query(ShopStore).filter(uuid_eq(ShopStore.id, shop_id)).first()
    if not shop:
        raise HTTPException(status_code=404, detail="店铺不存在")
    merchant = _merchant_for_store(db, shop)
    return shop, merchant


def _shop_brief(db: Session, shop: ShopStore, merchant: ShopMerchantAccount | None) -> MpStoreBriefOut:
    settings = (
        db.query(ShopStoreSettings).filter(uuid_eq(ShopStoreSettings.shop_id, shop.id)).first()
    )
    return MpStoreBriefOut(
        id=shop.id,
        tenant_id=shop.tenant_id,
        name=shop.name or "店铺",
        logo_url=shop.logo_url,
        status=shop.status,
        merchant_status=merchant.status if merchant else "not_onboarded",
        intro=(settings.intro if settings else None),
    )


def _product_card(p: ShopProduct) -> MpStoreProductCard:
    return MpStoreProductCard(
        id=p.id,
        type=p.type,
        name=p.name,
        subtitle=p.subtitle,
        cover_url=p.cover_url,
        price_cents=int(p.price_cents or 0),
        line_price_cents=p.line_price_cents,
        status=p.status,
        sales_count=int(p.sales_count or 0),
    )


def _active_entitlement(
    db: Session, buyer: ShopBuyer | None, product_id: UUID
) -> ShopEntitlement | None:
    if buyer is None:
        return None
    return (
        db.query(ShopEntitlement)
        .filter(
            uuid_eq(ShopEntitlement.buyer_id, buyer.id),
            uuid_eq(ShopEntitlement.product_id, product_id),
            ShopEntitlement.status == "active",
        )
        .order_by(ShopEntitlement.created_at.desc())
        .first()
    )


def get_storefront(
    db: Session,
    *,
    shop_id: UUID,
    q: str | None = None,
    type_filter: str | None = None,
    sort: str = "default",
    page: int = 1,
    page_size: int = 20,
) -> MpStorefrontResponse:
    shop, merchant = _get_store(db, shop_id)
    _assert_trade_open(shop, merchant)

    query = db.query(ShopProduct).filter(
        uuid_eq(ShopProduct.shop_id, shop_id),
        uuid_eq(ShopProduct.tenant_id, shop.tenant_id),
        ShopProduct.deleted_at.is_(None),
        ShopProduct.status == "on_sale",
    )
    if type_filter in ("course", "digital", "service"):
        query = query.filter(ShopProduct.type == type_filter)
    kw = (q or "").strip()
    if kw:
        like = f"%{kw}%"
        query = query.filter(or_(ShopProduct.name.ilike(like), ShopProduct.subtitle.ilike(like)))

    total = query.count()
    order_col = ShopProduct.updated_at.desc()
    if sort == "price_asc":
        order_col = ShopProduct.price_cents.asc()
    elif sort == "price_desc":
        order_col = ShopProduct.price_cents.desc()
    elif sort == "sales":
        order_col = ShopProduct.sales_count.desc()

    rows = (
        query.order_by(order_col)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return MpStorefrontResponse(
        shop=_shop_brief(db, shop, merchant),
        products=[_product_card(p) for p in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < total,
    )


def _lesson_previews(
    db: Session, product: ShopProduct, *, purchased: bool
) -> list[MpProductLessonPreview]:
    if product.type != "course":
        return []
    raw = content_cms_service.published_lessons_for_product(db, product)
    if not raw:
        raw = _default_lessons(product)
    out: list[MpProductLessonPreview] = []
    for i, les in enumerate(raw):
        is_trial = bool(les.get("is_trial"))
        out.append(
            MpProductLessonPreview(
                id=UUID(str(les["id"])),
                title=str(les.get("title") or f"课时{i + 1}"),
                duration_sec=int(les.get("duration_sec") or 0),
                is_trial=is_trial,
                trial_seconds=les.get("trial_seconds"),
                sort=int(les.get("sort") or i + 1),
                locked=not purchased and not is_trial,
            )
        )
    return out


def get_product_detail(
    db: Session,
    product_id: UUID,
    *,
    buyer: ShopBuyer | None = None,
) -> MpProductDetailOut:
    product = (
        db.query(ShopProduct)
        .filter(uuid_eq(ShopProduct.id, product_id), ShopProduct.deleted_at.is_(None))
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    shop, merchant = _get_store(db, product.shop_id)
    if product.tenant_id != shop.tenant_id:
        raise HTTPException(status_code=404, detail="商品不存在")

    ent = _active_entitlement(db, buyer, product.id)
    purchased = ent is not None
    # M03 浏览在售商品须店铺营业；已购用户看详情不受限（与 M06+ 一致）
    if not purchased:
        _assert_trade_open(shop, merchant)

    lessons = _lesson_previews(db, product, purchased=purchased)
    has_trial = any(l.is_trial for l in lessons)
    if purchased:
        purchase_state = "purchased"
    elif has_trial and product.status == "on_sale":
        purchase_state = "trial_available"
    else:
        purchase_state = "not_purchased"

    lesson_count = len(lessons) if product.type == "course" else None
    asset_count = None
    service_mode = None
    service_times = None
    if product.type == "digital":
        _, _, files = content_cms_service.package_files_for_product(db, product)
        asset_count = len(files)
    elif product.type == "service" and product.ref_type == "service_offer" and product.ref_id:
        from app.models.shop import ShopServiceOffer

        offer = (
            db.query(ShopServiceOffer)
            .filter(uuid_eq(ShopServiceOffer.id, product.ref_id))
            .first()
        )
        if offer:
            service_mode = offer.mode
            service_times = offer.total_times
            extra = product.extra or {}
            if service_times is None:
                service_times = extra.get("service_times")

    return MpProductDetailOut(
        id=product.id,
        shop_id=product.shop_id,
        tenant_id=product.tenant_id,
        type=product.type,
        name=product.name,
        subtitle=product.subtitle,
        cover_url=product.cover_url,
        price_cents=int(product.price_cents or 0),
        line_price_cents=product.line_price_cents,
        status=product.status,
        sales_count=int(product.sales_count or 0),
        purchase_state=purchase_state,
        entitlement_id=ent.id if ent else None,
        lesson_count=lesson_count,
        asset_count=asset_count,
        service_mode=service_mode,
        service_times=service_times,
        lessons=lessons,
        shop_name=shop.name,
        shop_status=shop.status,
        merchant_status=merchant.status if merchant else None,
    )
