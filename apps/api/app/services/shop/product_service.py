"""商家商品 + F6 机审 + P09 人审。对照 PRD §8.8 · 03#f6。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import User
from app.models.shop import (
    ShopChannelMapping,
    ShopMerchantAccount,
    ShopOrder,
    ShopPlatformCategory,
    ShopProduct,
    ShopProductReview,
    ShopStore,
)
from app.schemas.shop_platform import (
    ProductCreateRequest,
    ProductExportRequest,
    ProductOut,
    ProductPatchRequest,
    ProductRejectRequest,
    ProductReviewOut,
    ShopExportTaskOut,
)

# 公域列不适用（PRD 线框「—」）的商品状态
_MOUNT_NA_STATUSES = frozenset({"draft", "off_sale"})
_MOUNT_LABEL = {
    "mapped": "已挂载",
    "none": "未挂载",
    "rejected": "挂载被拒",
}

PRODUCT_TYPES = frozenset({"course", "digital", "service"})
EDITABLE_STATUSES = frozenset({"draft", "rejected", "off_sale"})
# action → (允许的当前状态, 目标状态, 非法边 422 文案)
# 禁止：draft→on_sale、rejected→on_sale（对照 PRD 四、商品状态机 / QC DR-4）
PRODUCT_TRANSITION_ACTIONS: dict[str, tuple[frozenset[str], str, str]] = {
    "submit_review": (
        frozenset({"draft", "rejected", "off_sale"}),
        "pending_review",
        "当前状态不可提审",
    ),
    "auto_reject": (
        frozenset({"draft", "rejected", "off_sale"}),
        "rejected",
        "当前状态不可提审",
    ),
    "publish": (
        frozenset({"approved", "off_sale"}),
        "on_sale",
        "仅审核通过或已下架商品可上架",
    ),
    "off_sale": (frozenset({"on_sale"}), "off_sale", "仅在售商品可下架"),
    "withdraw": (
        frozenset({"pending_review", "approved"}),
        "draft",
        "仅审核中或已通过可撤回",
    ),
    "approve": (frozenset({"pending_review"}), "approved", "商品状态不可审核"),
    "reject": (frozenset({"pending_review"}), "rejected", "商品状态不可审核"),
    "force_off": (
        frozenset({"draft", "pending_review", "rejected", "approved", "on_sale", "off_sale"}),
        "off_sale",
        "商品状态不可强制下架",
    ),
}


def transition_product(product: ShopProduct, action: str) -> str:
    spec = PRODUCT_TRANSITION_ACTIONS.get(action)
    if spec is None:
        raise HTTPException(status_code=422, detail="未知商品状态动作")
    allowed_from, to_status, err = spec
    if product.status not in allowed_from:
        raise HTTPException(status_code=422, detail=err)
    product.status = to_status
    return to_status


REF_BY_TYPE = {
    "course": "column",
    "digital": "digital_package",
    "service": "service_offer",
}
SENSITIVE_REJECT = ("违禁", "色情", "赌博")
SENSITIVE_FLAG = ("保证成交", "稳赚", "包过", "第一")


def _merchant(db: Session, tenant_id: UUID) -> ShopMerchantAccount:
    m = db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    if not m:
        raise HTTPException(status_code=404, detail="商家未入驻")
    if m.status == "closed":
        raise HTTPException(status_code=422, detail="商家已清退")
    if m.status == "suspended":
        raise HTTPException(status_code=422, detail="商家已暂停")
    return m


def ensure_default_shop(db: Session, tenant_id: UUID, merchant: ShopMerchantAccount) -> ShopStore:
    store = (
        db.query(ShopStore)
        .filter(uuid_eq(ShopStore.tenant_id, tenant_id), ShopStore.status != "closed")
        .order_by(ShopStore.created_at.asc())
        .first()
    )
    if store:
        return store
    slug = f"shop-{str(tenant_id).replace('-', '')[:8]}"
    store = ShopStore(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        merchant_id=merchant.id,
        name=(merchant.display_name or merchant.legal_name or "默认店铺")[:200],
        slug=slug,
        status="draft",
    )
    db.add(store)
    db.flush()
    return store


def _resolve_channel_mount(
    product_status: str, mapping_statuses: list[str]
) -> tuple[str | None, str]:
    """A02 公域列：已挂载 / 未挂载 / 挂载被拒 / —。"""
    if product_status in _MOUNT_NA_STATUSES and not mapping_statuses:
        return None, "—"
    if any(s == "blocked" for s in mapping_statuses):
        return "rejected", _MOUNT_LABEL["rejected"]
    if any(s in ("mapped", "paused") for s in mapping_statuses):
        return "mapped", _MOUNT_LABEL["mapped"]
    if product_status in _MOUNT_NA_STATUSES:
        return None, "—"
    return "none", _MOUNT_LABEL["none"]


def _category_labels(db: Session, category_id) -> tuple[str | None, str | None]:
    if not category_id:
        return None, None
    from app.models.shop import ShopPlatformCategory

    cat = (
        db.query(ShopPlatformCategory)
        .filter(uuid_eq(ShopPlatformCategory.id, category_id))
        .first()
    )
    if not cat:
        return None, None
    if cat.parent_id:
        parent = (
            db.query(ShopPlatformCategory)
            .filter(uuid_eq(ShopPlatformCategory.id, cat.parent_id))
            .first()
        )
        if parent:
            return cat.name, f"{parent.name} / {cat.name}"
    return cat.name, cat.name


def _product_out(
    p: ShopProduct,
    *,
    channel_mount: str | None = None,
    channel_mount_label: str = "—",
    created_by_name: str | None = None,
    category_name: str | None = None,
    category_path_label: str | None = None,
) -> ProductOut:
    return ProductOut(
        id=p.id,
        tenant_id=p.tenant_id,
        shop_id=p.shop_id,
        type=p.type,
        name=p.name,
        subtitle=p.subtitle,
        cover_url=p.cover_url,
        price_cents=p.price_cents,
        line_price_cents=p.line_price_cents,
        status=p.status,
        category_id=getattr(p, "category_id", None),
        category_name=category_name,
        category_path_label=category_path_label,
        ref_type=p.ref_type,
        ref_id=p.ref_id,
        last_review_id=p.last_review_id,
        compliance_flags=list(p.compliance_flags or []),
        refund_policy=p.refund_policy,
        sales_count=p.sales_count,
        extra=dict(p.extra or {}),
        channel_mount=channel_mount,
        channel_mount_label=channel_mount_label,
        created_by_name=created_by_name,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _mount_map_for_products(
    db: Session, tenant_id: UUID, product_ids: list[UUID]
) -> dict[UUID, list[str]]:
    if not product_ids:
        return {}
    rows = (
        db.query(ShopChannelMapping.product_id, ShopChannelMapping.status)
        .filter(
            uuid_eq(ShopChannelMapping.tenant_id, tenant_id),
            ShopChannelMapping.product_id.in_(product_ids),
            ShopChannelMapping.status.in_(
                ("mapped", "pending", "paused", "syncing", "blocked")
            ),
        )
        .all()
    )
    out: dict[UUID, list[str]] = {}
    for pid, st in rows:
        out.setdefault(pid, []).append(st)
    return out


def _creator_names(db: Session, products: list[ShopProduct]) -> dict[UUID, str]:
    ids = {p.created_by for p in products if p.created_by}
    if not ids:
        return {}
    users = db.query(User).filter(User.id.in_(list(ids))).all()
    return {u.id: (u.display_name or u.phone or "") for u in users}


def _enrich_products(db: Session, ctx: TenantContext, rows: list[ShopProduct]) -> list[ProductOut]:
    mounts = _mount_map_for_products(db, ctx.tenant_id, [r.id for r in rows])
    creators = _creator_names(db, rows)
    items: list[ProductOut] = []
    for r in rows:
        mount, label = _resolve_channel_mount(r.status, mounts.get(r.id, []))
        cname, cpath = _category_labels(db, getattr(r, "category_id", None))
        items.append(
            _product_out(
                r,
                channel_mount=mount,
                channel_mount_label=label,
                created_by_name=creators.get(r.created_by) if r.created_by else None,
                category_name=cname,
                category_path_label=cpath,
            )
        )
    return items


def _product_base_query(
    db: Session,
    ctx: TenantContext,
    *,
    shop_id: UUID | None = None,
    status_filter: str | None = None,
    type_filter: str | None = None,
    q: str | None = None,
    channel_mount: str | None = None,
    price_min_cents: int | None = None,
    price_max_cents: int | None = None,
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
):
    query = db.query(ShopProduct).filter(
        uuid_eq(ShopProduct.tenant_id, ctx.tenant_id),
        ShopProduct.deleted_at.is_(None),
    )
    if shop_id:
        query = query.filter(uuid_eq(ShopProduct.shop_id, shop_id))
    if status_filter:
        query = query.filter(ShopProduct.status == status_filter)
    if type_filter:
        query = query.filter(ShopProduct.type == type_filter)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(ShopProduct.name.ilike(like), ShopProduct.subtitle.ilike(like)))
    if price_min_cents is not None:
        query = query.filter(ShopProduct.price_cents >= price_min_cents)
    if price_max_cents is not None:
        query = query.filter(ShopProduct.price_cents <= price_max_cents)
    if updated_from is not None:
        query = query.filter(ShopProduct.updated_at >= updated_from)
    if updated_to is not None:
        query = query.filter(ShopProduct.updated_at <= updated_to)
    if channel_mount in ("mapped", "none", "rejected"):
        mapped_ids = (
            db.query(ShopChannelMapping.product_id)
            .filter(
                uuid_eq(ShopChannelMapping.tenant_id, ctx.tenant_id),
                ShopChannelMapping.status.in_(("mapped", "paused")),
            )
            .distinct()
        )
        blocked_ids = (
            db.query(ShopChannelMapping.product_id)
            .filter(
                uuid_eq(ShopChannelMapping.tenant_id, ctx.tenant_id),
                ShopChannelMapping.status == "blocked",
            )
            .distinct()
        )
        if channel_mount == "mapped":
            # 阻断优先：同时有 mapped+blocked 时归 rejected，不进已挂载筛
            query = query.filter(
                ShopProduct.id.in_(mapped_ids),
                ~ShopProduct.id.in_(blocked_ids),
            )
        elif channel_mount == "rejected":
            query = query.filter(ShopProduct.id.in_(blocked_ids))
        else:
            # 未挂载：非 draft/off_sale 且无已挂载/暂停，且无阻断（阻断优先归 rejected）
            query = query.filter(
                ~ShopProduct.status.in_(list(_MOUNT_NA_STATUSES)),
                ~ShopProduct.id.in_(mapped_ids),
                ~ShopProduct.id.in_(blocked_ids),
            )
    return query


def _status_counts(db: Session, ctx: TenantContext, *, shop_id: UUID | None = None) -> dict[str, int]:
    q = db.query(ShopProduct.status, func.count()).filter(
        uuid_eq(ShopProduct.tenant_id, ctx.tenant_id),
        ShopProduct.deleted_at.is_(None),
    )
    if shop_id:
        q = q.filter(uuid_eq(ShopProduct.shop_id, shop_id))
    rows = q.group_by(ShopProduct.status).all()
    counts = {st: int(n) for st, n in rows}
    counts["all"] = sum(counts.values())
    return counts


def _validate_content_ref(
    db: Session,
    tenant_id: UUID,
    product_type: str,
    ref_type: str | None,
    ref_id: UUID | None,
    *,
    required: bool,
) -> None:
    """A03：课→专栏 / 资料→资料包 / 服务→服务定义。"""
    expect = REF_BY_TYPE.get(product_type)
    if not expect:
        return
    if not ref_id:
        if required:
            labels = {"column": "关联专栏", "digital_package": "关联资料包", "service_offer": "关联服务"}
            raise HTTPException(status_code=422, detail=f"请选择{labels.get(expect, '关联内容')}")
        return
    if ref_type and ref_type != expect:
        raise HTTPException(status_code=422, detail="关联内容类型与商品类型不匹配")
    if product_type == "course":
        from app.models.shop import ShopColumn, ShopLesson

        col = (
            db.query(ShopColumn)
            .filter(
                uuid_eq(ShopColumn.id, ref_id),
                uuid_eq(ShopColumn.tenant_id, tenant_id),
                ShopColumn.deleted_at.is_(None),
            )
            .first()
        )
        if not col or col.status != "published":
            raise HTTPException(status_code=422, detail="请选择已发布的专栏")
        pub = (
            db.query(ShopLesson)
            .filter(
                uuid_eq(ShopLesson.column_id, col.id),
                ShopLesson.deleted_at.is_(None),
                ShopLesson.status == "published",
            )
            .count()
        )
        if pub < 1:
            raise HTTPException(status_code=422, detail="专栏须至少有 1 个已发布课时")
    elif product_type == "digital":
        from app.models.shop import ShopDigitalAsset, ShopDigitalPackage

        pkg = (
            db.query(ShopDigitalPackage)
            .filter(
                uuid_eq(ShopDigitalPackage.id, ref_id),
                uuid_eq(ShopDigitalPackage.tenant_id, tenant_id),
                ShopDigitalPackage.deleted_at.is_(None),
            )
            .first()
        )
        if not pkg or pkg.status != "published":
            raise HTTPException(status_code=422, detail="请选择已发布的资料包")
        n = db.query(ShopDigitalAsset).filter(uuid_eq(ShopDigitalAsset.package_id, pkg.id)).count()
        if n < 1:
            raise HTTPException(status_code=422, detail="资料包须至少有 1 个文件")
    elif product_type == "service":
        from app.models.shop import ShopServiceOffer

        offer = (
            db.query(ShopServiceOffer)
            .filter(
                uuid_eq(ShopServiceOffer.id, ref_id),
                uuid_eq(ShopServiceOffer.tenant_id, tenant_id),
                ShopServiceOffer.deleted_at.is_(None),
            )
            .first()
        )
        if not offer or offer.status != "published":
            raise HTTPException(status_code=422, detail="请选择已发布的服务")


def _get_owned(db: Session, tenant_id: UUID, product_id: UUID) -> ShopProduct:
    p = (
        db.query(ShopProduct)
        .filter(
            uuid_eq(ShopProduct.id, product_id),
            uuid_eq(ShopProduct.tenant_id, tenant_id),
            ShopProduct.deleted_at.is_(None),
        )
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")
    return p


def run_auto_review(name: str, subtitle: str | None) -> tuple[str, list[dict]]:
    text = f"{name} {subtitle or ''}"
    flags: list[dict] = []
    for w in SENSITIVE_REJECT:
        if w in text:
            flags.append(
                {"rule": "sensitive_word", "level": "reject", "field": "name", "snippet": w, "message": "违禁词"}
            )
    if flags:
        return "reject", flags
    for w in SENSITIVE_FLAG:
        if w in text:
            flags.append(
                {
                    "rule": "exaggerated_claim",
                    "level": "flag",
                    "field": "subtitle" if (subtitle and w in subtitle) else "name",
                    "snippet": w,
                    "message": "夸大承诺",
                }
            )
    if flags:
        return "flag", flags
    return "pass", []


def list_products(
    db: Session,
    ctx: TenantContext,
    *,
    shop_id: UUID | None = None,
    status_filter: str | None = None,
    type_filter: str | None = None,
    q: str | None = None,
    channel_mount: str | None = None,
    price_min_cents: int | None = None,
    price_max_cents: int | None = None,
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ProductOut], int, dict[str, int]]:
    query = _product_base_query(
        db,
        ctx,
        shop_id=shop_id,
        status_filter=status_filter,
        type_filter=type_filter,
        q=q,
        channel_mount=channel_mount,
        price_min_cents=price_min_cents,
        price_max_cents=price_max_cents,
        updated_from=updated_from,
        updated_to=updated_to,
    )
    total = query.count()
    rows = (
        query.order_by(ShopProduct.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _enrich_products(db, ctx, rows), total, _status_counts(db, ctx, shop_id=shop_id)


def export_products_csv(
    db: Session,
    ctx: TenantContext,
    *,
    shop_id: UUID | None = None,
    status_filter: str | None = None,
    type_filter: str | None = None,
    q: str | None = None,
    channel_mount: str | None = None,
    price_min_cents: int | None = None,
    price_max_cents: int | None = None,
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    import csv
    import io

    query = _product_base_query(
        db,
        ctx,
        shop_id=shop_id,
        status_filter=status_filter,
        type_filter=type_filter,
        q=q,
        channel_mount=channel_mount,
        price_min_cents=price_min_cents,
        price_max_cents=price_max_cents,
        updated_from=updated_from,
        updated_to=updated_to,
    )
    total = query.count()
    if raise_too_many and total > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    rows = query.order_by(ShopProduct.updated_at.desc()).limit(5000).all()
    items = _enrich_products(db, ctx, rows)
    type_label = {"course": "课程", "digital": "资料", "service": "服务"}
    status_label = {
        "draft": "草稿",
        "pending_review": "审核中",
        "approved": "已通过",
        "on_sale": "在售",
        "rejected": "已驳回",
        "off_sale": "已下架",
    }
    default_headers = ["名称", "类型", "售价(分)", "销量", "状态", "关联", "公域", "创建人", "创建时间", "更新时间"]
    col_map = {
        "name": ["名称"],
        "type": ["类型"],
        "price": ["售价(分)"],
        "sales_count": ["销量"],
        "status": ["状态"],
        "ref": ["关联"],
        "channel_mount": ["公域"],
        "created_by": ["创建人"],
        "created_at": ["创建时间"],
        "updated_at": ["更新时间"],
    }
    if columns:
        headers: list[str] = []
        seen: set[str] = set()
        for key in columns:
            for h in col_map.get(key, []):
                if h not in seen:
                    seen.add(h)
                    headers.append(h)
        headers = headers or default_headers
    else:
        headers = default_headers
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for o in items:
        values = {
            "名称": o.name,
            "类型": type_label.get(o.type, o.type),
            "售价(分)": o.price_cents,
            "销量": o.sales_count,
            "状态": status_label.get(o.status, o.status),
            "关联": o.ref_type or "未关联",
            "公域": o.channel_mount_label,
            "创建人": o.created_by_name or "",
            "创建时间": o.created_at.isoformat() if o.created_at else "",
            "更新时间": o.updated_at.isoformat() if o.updated_at else "",
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_product_export_task(
    db: Session, ctx: TenantContext, body: ProductExportRequest | None = None
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or ProductExportRequest()
    filters = {
        "shop_id": str(body.shop_id) if body.shop_id else None,
        "status": body.status,
        "type": body.type,
        "q": body.q,
        "channel_mount": body.channel_mount,
        "price_min_cents": body.price_min_cents,
        "price_max_cents": body.price_max_cents,
        "updated_from": str(body.updated_from) if body.updated_from else None,
        "updated_to": str(body.updated_to) if body.updated_to else None,
        "columns": body.columns,
    }
    csv_text = export_products_csv(
        db,
        ctx,
        shop_id=body.shop_id,
        status_filter=body.status,
        type_filter=body.type,
        q=body.q,
        channel_mount=body.channel_mount,
        price_min_cents=body.price_min_cents,
        price_max_cents=body.price_max_cents,
        updated_from=body.updated_from,
        updated_to=body.updated_to,
        columns=body.columns,
        raise_too_many=True,
    )
    return export_task_service.persist_csv_task(
        db,
        ctx,
        resource="products",
        file_name="shop-products.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_product_export_task(db: Session, ctx: TenantContext, task_id: UUID) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task(db, ctx, task_id, "products")


def read_product_export_file(db: Session, ctx: TenantContext, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file(db, ctx, task_id, "products")


def create_product(db: Session, ctx: TenantContext, payload: ProductCreateRequest) -> ProductOut:
    merchant = _merchant(db, ctx.tenant_id)
    if payload.type not in PRODUCT_TYPES:
        raise HTTPException(status_code=422, detail="商品类型无效")
    if not (payload.name or "").strip():
        raise HTTPException(status_code=422, detail="请填写商品名称")
    if payload.price_cents < 0:
        raise HTTPException(status_code=422, detail="价格不能为负")
    if payload.line_price_cents is not None and payload.line_price_cents < payload.price_cents:
        raise HTTPException(status_code=422, detail="划线价不能低于售价")

    expect_ref = REF_BY_TYPE.get(payload.type)
    ref_type = payload.ref_type or (expect_ref if payload.ref_id else None)
    _validate_content_ref(
        db, ctx.tenant_id, payload.type, ref_type, payload.ref_id, required=False
    )

    if payload.shop_id:
        shop = (
            db.query(ShopStore)
            .filter(
                uuid_eq(ShopStore.id, payload.shop_id),
                uuid_eq(ShopStore.tenant_id, ctx.tenant_id),
            )
            .first()
        )
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
    else:
        shop = ensure_default_shop(db, ctx.tenant_id, merchant)

    from app.services.shop import category_service, store_settings_service

    category_id = payload.category_id
    if category_id:
        category_service.get_enabled_category(db, category_id)
    else:
        # 新建默认：店铺默认类目 → 首个启用类目
        category_id = shop.default_category_id or category_service.first_enabled_category_id(db)
        if category_id:
            try:
                category_service.get_enabled_category(db, category_id)
            except HTTPException:
                category_id = category_service.first_enabled_category_id(db)

    extra = dict(payload.extra or {})
    if payload.service_times is not None:
        extra["service_times"] = int(payload.service_times)
    elif payload.type == "service" and "service_times" not in extra:
        extra["service_times"] = 1

    p = ShopProduct(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        shop_id=shop.id,
        type=payload.type,
        name=payload.name.strip(),
        subtitle=(payload.subtitle or None),
        cover_url=payload.cover_url,
        price_cents=payload.price_cents,
        line_price_cents=payload.line_price_cents,
        status="draft",
        category_id=category_id,
        ref_type=ref_type,
        ref_id=payload.ref_id,
        compliance_flags=[],
        refund_policy=payload.refund_policy
        or store_settings_service.get_default_refund_policy(db, shop.id),
        extra=extra,
        created_by=ctx.user.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    cname, cpath = _category_labels(db, p.category_id)
    return _product_out(p, category_name=cname, category_path_label=cpath)


def get_product(db: Session, ctx: TenantContext, product_id: UUID) -> ProductOut:
    p = _get_owned(db, ctx.tenant_id, product_id)
    cname, cpath = _category_labels(db, getattr(p, "category_id", None))
    return _product_out(p, category_name=cname, category_path_label=cpath)


def patch_product(db: Session, ctx: TenantContext, product_id: UUID, payload: ProductPatchRequest) -> ProductOut:
    p = _get_owned(db, ctx.tenant_id, product_id)
    if p.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=422, detail="当前状态不可编辑核心字段")
    if payload.name is not None:
        p.name = payload.name.strip()
    if payload.subtitle is not None:
        p.subtitle = payload.subtitle
    if payload.cover_url is not None:
        p.cover_url = payload.cover_url
    if payload.price_cents is not None:
        if payload.price_cents < 0:
            raise HTTPException(status_code=422, detail="价格不能为负")
        p.price_cents = payload.price_cents
    if payload.line_price_cents is not None:
        p.line_price_cents = payload.line_price_cents
    if p.line_price_cents is not None and p.line_price_cents < p.price_cents:
        raise HTTPException(status_code=422, detail="划线价不能低于售价")
    if payload.refund_policy is not None:
        p.refund_policy = payload.refund_policy
    data = payload.model_dump(exclude_unset=True)
    if "ref_id" in data or "ref_type" in data:
        new_ref_id = data.get("ref_id", p.ref_id)
        expect = REF_BY_TYPE.get(p.type)
        new_ref_type = data.get("ref_type") or (expect if new_ref_id else None)
        _validate_content_ref(
            db, ctx.tenant_id, p.type, new_ref_type, new_ref_id, required=False
        )
        p.ref_id = new_ref_id
        p.ref_type = new_ref_type
    if payload.category_id is not None:
        from app.services.shop import category_service

        category_service.get_enabled_category(db, payload.category_id)
        p.category_id = payload.category_id
    if payload.extra is not None:
        merged = dict(p.extra or {})
        merged.update(payload.extra)
        p.extra = merged
    db.commit()
    db.refresh(p)
    cname, cpath = _category_labels(db, p.category_id)
    return _product_out(p, category_name=cname, category_path_label=cpath)


def submit_review(db: Session, ctx: TenantContext, product_id: UUID, remark: str | None = None) -> dict:
    p = _get_owned(db, ctx.tenant_id, product_id)
    if p.status not in ("draft", "rejected", "off_sale"):
        raise HTTPException(status_code=422, detail="当前状态不可提审")
    if not (p.cover_url or "").strip():
        raise HTTPException(status_code=422, detail="请补全封面")
    _validate_content_ref(
        db, ctx.tenant_id, p.type, p.ref_type, p.ref_id, required=True
    )
    from app.services.shop import category_service

    if not p.category_id:
        raise HTTPException(status_code=422, detail="请补全平台类目")
    category_service.get_enabled_category(db, p.category_id)

    auto_result, auto_flags = run_auto_review(p.name, p.subtitle)
    snap = {
        "name": p.name,
        "subtitle": p.subtitle,
        "type": p.type,
        "price_cents": p.price_cents,
        "refund_policy": p.refund_policy,
        "category_id": str(p.category_id) if p.category_id else None,
        "ref_type": p.ref_type,
        "ref_id": str(p.ref_id) if p.ref_id else None,
        "cover_url": p.cover_url,
        "intro": (p.extra or {}).get("intro"),
        "remark": remark,
    }
    review = ShopProductReview(
        id=uuid.uuid4(),
        product_id=p.id,
        tenant_id=p.tenant_id,
        snapshot_json=snap,
        auto_result=auto_result,
        auto_flags=auto_flags,
        manual_result="pending",
        submitted_by=ctx.user.id,
    )
    db.add(review)
    db.flush()
    p.last_review_id = review.id
    p.compliance_flags = auto_flags

    if auto_result in ("flag", "reject"):
        from app.services.shop import p07_moderation_service as p07svc

        p07svc.ingest_from_auto_review(
            db,
            product=p,
            review_id=review.id,
            auto_result=auto_result,
            auto_flags=auto_flags,
        )

    if auto_result == "reject":
        transition_product(p, "auto_reject")
        review.manual_result = "rejected"
        review.reject_reason = "机审未通过，请修改后提交审核"
        review.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=422, detail="机审未通过，请修改后提交审核")

    transition_product(p, "submit_review")
    db.commit()
    return {
        "id": str(p.id),
        "product_id": str(p.id),
        "status": p.status,
        "review_id": str(review.id),
        "auto_result": auto_result,
        "auto_flags": auto_flags,
        "compliance_summary": "；".join(f.get("message", "") for f in auto_flags) or None,
    }


def _product_out_with_category(db: Session, p: ShopProduct) -> ProductOut:
    cname, cpath = _category_labels(db, getattr(p, "category_id", None))
    return _product_out(p, category_name=cname, category_path_label=cpath)


def publish_product(db: Session, ctx: TenantContext, product_id: UUID) -> ProductOut:
    p = _get_owned(db, ctx.tenant_id, product_id)
    transition_product(p, "publish")
    db.commit()
    db.refresh(p)
    return _product_out_with_category(db, p)


def off_sale_product(db: Session, ctx: TenantContext, product_id: UUID) -> ProductOut:
    p = _get_owned(db, ctx.tenant_id, product_id)
    transition_product(p, "off_sale")
    # A02-B：已挂载映射自动暂停同步
    from app.services.shop import channel_service

    channel_service.pause_mapped_for_product(
        db, ctx, p.id, summary="商品下架自动暂停同步"
    )
    db.commit()
    db.refresh(p)
    return _product_out_with_category(db, p)


def soft_delete_product(db: Session, ctx: TenantContext, product_id: UUID) -> None:
    """A02-C：仅草稿/已下架；无未完成订单；无活跃公域映射。"""
    p = _get_owned(db, ctx.tenant_id, product_id)
    if p.status not in ("draft", "off_sale"):
        raise HTTPException(status_code=422, detail="在售/审核中不可删")
    pre = delete_precheck(db, ctx, product_id)
    if not pre["can_delete"]:
        if "channel_mappings" in pre["blockers"]:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "请先解除公域映射",
                    "mappings": pre["mappings"],
                },
            )
        if "open_orders" in pre["blockers"]:
            raise HTTPException(status_code=422, detail="存在未完成订单")
        raise HTTPException(status_code=422, detail="当前状态不可删除")
    p.deleted_at = datetime.now(timezone.utc)
    db.commit()


def delete_precheck(db: Session, ctx: TenantContext, product_id: UUID) -> dict:
    from app.models.shop import ShopChannelMapping, ShopOrder

    p = _get_owned(db, ctx.tenant_id, product_id)
    blockers: list[str] = []
    if p.status not in ("draft", "off_sale"):
        blockers.append("bad_status")
    open_orders = (
        db.query(ShopOrder)
        .filter(
            uuid_eq(ShopOrder.tenant_id, ctx.tenant_id),
            uuid_eq(ShopOrder.product_id, p.id),
            ShopOrder.status.in_(("pending_payment", "claim_pending", "refunding")),
        )
        .count()
    )
    if open_orders > 0:
        blockers.append("open_orders")
    mapping_rows = (
        db.query(ShopChannelMapping)
        .filter(
            uuid_eq(ShopChannelMapping.tenant_id, ctx.tenant_id),
            uuid_eq(ShopChannelMapping.product_id, p.id),
            ShopChannelMapping.status.in_(
                ("mapped", "pending", "paused", "syncing", "blocked")
            ),
        )
        .all()
    )
    mappings = [
        {
            "id": str(m.id),
            "channel": m.channel,
            "channel_label": "抖店" if m.channel == "douyin" else "抖音课程库",
            "status": m.status,
            "channel_product_id": m.channel_product_id,
        }
        for m in mapping_rows
    ]
    if mappings:
        blockers.append("channel_mappings")
    return {
        "product_id": str(p.id),
        "product_name": p.name,
        "status": p.status,
        "can_delete": len(blockers) == 0,
        "open_order_count": int(open_orders),
        "mappings": mappings,
        "blockers": blockers,
    }


def batch_submit_review(
    db: Session, ctx: TenantContext, product_ids: list[UUID]
) -> dict:
    ids = list(dict.fromkeys(product_ids))[:50]
    if not ids:
        raise HTTPException(status_code=422, detail="未选择商品")
    ok: list[str] = []
    fail: list[dict] = []
    for pid in ids:
        try:
            submit_review(db, ctx, pid)
            ok.append(str(pid))
        except HTTPException as e:
            fail.append({"product_id": str(pid), "detail": e.detail})
    return {"ok_count": len(ok), "fail_count": len(fail), "ok": ok, "fail": fail}


def batch_off_sale(db: Session, ctx: TenantContext, product_ids: list[UUID]) -> dict:
    ids = list(dict.fromkeys(product_ids))[:50]
    if not ids:
        raise HTTPException(status_code=422, detail="未选择商品")
    ok: list[str] = []
    fail: list[dict] = []
    for pid in ids:
        try:
            off_sale_product(db, ctx, pid)
            ok.append(str(pid))
        except HTTPException as e:
            fail.append({"product_id": str(pid), "detail": e.detail})
    return {"ok_count": len(ok), "fail_count": len(fail), "ok": ok, "fail": fail}


def withdraw_product(db: Session, ctx: TenantContext, product_id: UUID) -> ProductOut:
    """撤回：审核中/已通过 → 草稿，便于再编辑。对照 PRD #a02 / #a03。"""
    p = _get_owned(db, ctx.tenant_id, product_id)
    if p.status not in ("pending_review", "approved"):
        raise HTTPException(status_code=422, detail="仅审核中或已通过可撤回")
    transition_product(p, "withdraw")
    db.commit()
    db.refresh(p)
    return _product_out_with_category(db, p)


REJECT_CODES = {
    "sensitive": "敏感内容",
    "qualification": "资质不符",
    "false_ad": "虚假宣传",
    "other": "其他",
}
REVIEW_SORT = {
    "product_name": ShopProduct.name,
    "merchant_name": ShopMerchantAccount.display_name,
    "auto_result": ShopProductReview.auto_result,
    "submitted_at": ShopProductReview.submitted_at,
    "reviewed_at": ShopProductReview.reviewed_at,
}


def _p09_meta(snap: dict | None) -> dict:
    return dict((snap or {}).get("_p09") or {})


def _paid_order_count(db: Session, product_id: UUID) -> int:
    return int(
        db.query(func.count(ShopOrder.id))
        .filter(uuid_eq(ShopOrder.product_id, product_id), ShopOrder.paid_at.isnot(None))
        .scalar()
        or 0
    )


def _has_public_mapping(db: Session, product_id: UUID) -> bool:
    row = (
        db.query(ShopChannelMapping.id)
        .filter(uuid_eq(ShopChannelMapping.product_id, product_id))
        .first()
    )
    return row is not None


def _user_name(db: Session, user_id: UUID | None) -> str | None:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return None
    return u.display_name or u.phone


def _audit_log(r: ShopProductReview, submitted_name: str | None, reviewer_name: str | None) -> list[dict]:
    log: list[dict] = []
    if r.submitted_at:
        log.append(
            {
                "at": r.submitted_at.isoformat() if hasattr(r.submitted_at, "isoformat") else str(r.submitted_at),
                "label": f"提交审核{(' · ' + submitted_name) if submitted_name else ''}",
            }
        )
    log.append({"at": None, "label": f"机审 {r.auto_result}"})
    if r.reviewed_at:
        action = {"approved": "人审通过", "rejected": "人审驳回"}.get(r.manual_result, "人审")
        who = f" · {reviewer_name}" if reviewer_name else ""
        log.append(
            {
                "at": r.reviewed_at.isoformat() if hasattr(r.reviewed_at, "isoformat") else str(r.reviewed_at),
                "label": f"{action}{who}",
            }
        )
    return log


def _review_out(db: Session, r: ShopProductReview, product: ShopProduct | None = None) -> ProductReviewOut:
    p = product or db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, r.product_id)).first()
    merchant = (
        db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, r.tenant_id)).first()
        if r.tenant_id
        else None
    )
    store = None
    if p:
        store = db.query(ShopStore).filter(uuid_eq(ShopStore.id, p.shop_id)).first()
    snap = dict(r.snapshot_json or {})
    cat_id = p.category_id if p else snap.get("category_id")
    cname, cpath = _category_labels(db, cat_id)
    meta = _p09_meta(snap)
    submitted_name = _user_name(db, r.submitted_by)
    reviewer_name = _user_name(db, r.reviewer_id)
    return ProductReviewOut(
        id=r.id,
        product_id=r.product_id,
        tenant_id=r.tenant_id,
        product_name=(p.name if p else None) or snap.get("name"),
        product_type=(p.type if p else None) or snap.get("type"),
        product_status=p.status if p else None,
        merchant_name=merchant.display_name if merchant else None,
        merchant_code=merchant.merchant_no if merchant else None,
        shop_name=store.name if store else None,
        category_name=cname,
        category_path=cpath,
        plan_label=merchant.plan_label if merchant else None,
        entity_type=merchant.entity_type if merchant else None,
        entity_status=merchant.status if merchant else None,
        snapshot_json=snap,
        auto_result=r.auto_result,
        auto_flags=list(r.auto_flags or []),
        manual_result=r.manual_result,
        reject_reason=r.reject_reason,
        reject_code=meta.get("reject_code"),
        internal_note=meta.get("internal_note"),
        reviewer_id=r.reviewer_id,
        reviewer_name=reviewer_name,
        reviewed_at=r.reviewed_at,
        submitted_by=r.submitted_by,
        submitted_by_name=submitted_name,
        submitted_at=r.submitted_at,
        paid_order_count=_paid_order_count(db, r.product_id) if r.product_id else 0,
        first_public_domain=_has_public_mapping(db, r.product_id) if r.product_id else False,
        audit_log=_audit_log(r, submitted_name, reviewer_name),
    )


def _review_counts(db: Session) -> tuple[int, int, int]:
    pending = (
        db.query(func.count(ShopProductReview.id))
        .filter(ShopProductReview.manual_result == "pending")
        .scalar()
        or 0
    )
    flagged = (
        db.query(func.count(ShopProductReview.id))
        .filter(
            ShopProductReview.manual_result == "pending",
            ShopProductReview.auto_result == "flag",
        )
        .scalar()
        or 0
    )
    reviewed = (
        db.query(func.count(ShopProductReview.id))
        .filter(ShopProductReview.manual_result.in_(("approved", "rejected")))
        .scalar()
        or 0
    )
    return int(pending), int(flagged), int(reviewed)


def _category_options(db: Session) -> list[dict]:
    rows = (
        db.query(ShopPlatformCategory)
        .filter(ShopPlatformCategory.status == "enabled")
        .order_by(ShopPlatformCategory.name.asc())
        .limit(200)
        .all()
    )
    return [{"id": str(c.id), "name": c.name} for c in rows]


def list_product_reviews(
    db: Session,
    *,
    status_filter: str | None = "pending",
    queue: str | None = None,
    q: str | None = None,
    auto_result: str | None = None,
    category_id: UUID | None = None,
    product_status: str | None = None,
    submitted_from: datetime | None = None,
    submitted_to: datetime | None = None,
    plan_label: str | None = None,
    first_public: bool | None = None,
    sort_by: str | None = None,
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ProductReviewOut], int, dict]:
    query = (
        db.query(ShopProductReview)
        .outerjoin(ShopProduct, ShopProduct.id == ShopProductReview.product_id)
        .outerjoin(ShopMerchantAccount, ShopMerchantAccount.tenant_id == ShopProductReview.tenant_id)
    )
    if queue == "reviewed":
        query = query.filter(ShopProductReview.manual_result.in_(("approved", "rejected")))
    elif queue == "flagged":
        query = query.filter(
            ShopProductReview.manual_result == "pending",
            ShopProductReview.auto_result == "flag",
        )
    elif status_filter:
        query = query.filter(ShopProductReview.manual_result == status_filter)
    if auto_result:
        query = query.filter(ShopProductReview.auto_result == auto_result)
    if category_id:
        query = query.filter(uuid_eq(ShopProduct.category_id, category_id))
    if product_status:
        query = query.filter(ShopProduct.status == product_status)
    if submitted_from is not None:
        query = query.filter(ShopProductReview.submitted_at >= submitted_from)
    if submitted_to is not None:
        query = query.filter(ShopProductReview.submitted_at <= submitted_to)
    if plan_label and plan_label.strip():
        query = query.filter(ShopMerchantAccount.plan_label.ilike(f"%{plan_label.strip()}%"))
    if first_public is True:
        query = query.filter(
            ShopProduct.id.in_(db.query(ShopChannelMapping.product_id).filter(ShopChannelMapping.product_id.isnot(None)))
        )
    elif first_public is False:
        query = query.filter(
            ~ShopProduct.id.in_(
                db.query(ShopChannelMapping.product_id).filter(ShopChannelMapping.product_id.isnot(None))
            )
        )
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                ShopProduct.name.ilike(like),
                ShopMerchantAccount.display_name.ilike(like),
                ShopMerchantAccount.legal_name.ilike(like),
            )
        )
    sort_col = REVIEW_SORT.get(sort_by or "", ShopProductReview.submitted_at)
    if queue == "reviewed" and not sort_by:
        sort_col = ShopProductReview.reviewed_at
    order = sort_col.asc() if sort_dir == "asc" else sort_col.desc()
    total = query.count()
    rows = (
        query.order_by(order, ShopProductReview.submitted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    out = [_review_out(db, r) for r in rows]
    pending, flagged, reviewed = _review_counts(db)
    extra = {
        "pending_count": pending,
        "flagged_count": flagged,
        "reviewed_count": reviewed,
        "category_options": _category_options(db),
    }
    return out, total, extra


def get_product_review(db: Session, review_id: UUID) -> ProductReviewOut:
    r = db.query(ShopProductReview).filter(uuid_eq(ShopProductReview.id, review_id)).first()
    if not r:
        raise HTTPException(status_code=404, detail="审核单不存在")
    return _review_out(db, r)


def buyer_preview(db: Session, review_id: UUID) -> dict:
    """P09 预览买家页：快照 + 未上架水印。对照 #p09-review-panel。"""
    out = get_product_review(db, review_id)
    snap = dict(out.snapshot_json or {})
    return {
        "review_id": str(out.id),
        "product_id": str(out.product_id),
        "product_name": out.product_name,
        "subtitle": snap.get("subtitle"),
        "price_cents": snap.get("price_cents"),
        "cover_url": snap.get("cover_url"),
        "intro": snap.get("intro"),
        "product_type": out.product_type,
        "shop_name": out.shop_name,
        "merchant_name": out.merchant_name,
        "watermark": "未上架",
        "product_status": out.product_status,
    }


def approve_review(
    db: Session, user: User, review_id: UUID, note: str | None = None
) -> ProductReviewOut:
    r = db.query(ShopProductReview).filter(uuid_eq(ShopProductReview.id, review_id)).first()
    if not r:
        raise HTTPException(status_code=404, detail="审核单不存在")
    if r.manual_result != "pending":
        raise HTTPException(status_code=422, detail="已出队不可审")
    note_s = (note or "").strip()
    if r.auto_result == "reject" and len(note_s) < 4:
        raise HTTPException(status_code=422, detail="请填写覆写备注")
    p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, r.product_id)).first()
    if not p or p.status != "pending_review":
        raise HTTPException(status_code=422, detail="商品状态不可审核")
    if note_s:
        snap = dict(r.snapshot_json or {})
        meta = _p09_meta(snap)
        meta["internal_note"] = note_s
        snap["_p09"] = meta
        r.snapshot_json = snap
    r.manual_result = "approved"
    r.reviewer_id = user.id
    r.reviewed_at = datetime.now(timezone.utc)
    transition_product(p, "approve")
    p.last_review_id = r.id
    db.commit()
    return _review_out(db, r, p)


def reject_review(db: Session, user: User, review_id: UUID, payload: ProductRejectRequest) -> ProductReviewOut:
    reason = (payload.reject_reason or "").strip()
    if len(reason) < 4:
        raise HTTPException(status_code=422, detail="请填写驳回原因")
    code = (payload.reject_code or "").strip() or None
    if code and code not in REJECT_CODES:
        raise HTTPException(status_code=422, detail="驳回原因码无效")
    r = db.query(ShopProductReview).filter(uuid_eq(ShopProductReview.id, review_id)).first()
    if not r:
        raise HTTPException(status_code=404, detail="审核单不存在")
    if r.manual_result != "pending":
        raise HTTPException(status_code=422, detail="已出队不可审")
    p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, r.product_id)).first()
    if not p or p.status != "pending_review":
        raise HTTPException(status_code=422, detail="商品状态不可审核")
    if code:
        snap = dict(r.snapshot_json or {})
        meta = _p09_meta(snap)
        meta["reject_code"] = code
        snap["_p09"] = meta
        r.snapshot_json = snap
    r.manual_result = "rejected"
    r.reject_reason = reason
    r.reviewer_id = user.id
    r.reviewed_at = datetime.now(timezone.utc)
    transition_product(p, "reject")
    p.last_review_id = r.id
    db.commit()
    return _review_out(db, r, p)


def force_off_from_review(db: Session, user: User, review_id: UUID, reason: str) -> ProductReviewOut:
    text = (reason or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="请填写下架原因")
    r = db.query(ShopProductReview).filter(uuid_eq(ShopProductReview.id, review_id)).first()
    if not r:
        raise HTTPException(status_code=404, detail="审核单不存在")
    p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, r.product_id)).first()
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=422, detail="商品不存在")
    paid = _paid_order_count(db, p.id)
    if p.status != "on_sale" and paid < 1:
        raise HTTPException(status_code=422, detail="商品未在售")
    transition_product(p, "force_off")
    extra = dict(p.extra or {})
    extra["p09_force_off"] = {"review_id": str(r.id), "reason": text}
    p.extra = extra
    from app.services.shop import channel_service

    channel_service.block_mapped_for_moderation(
        db,
        p.id,
        operator_id=user.id,
        summary=f"商品审核强制下架：{text}",
    )
    snap = dict(r.snapshot_json or {})
    meta = _p09_meta(snap)
    meta["force_off_reason"] = text
    snap["_p09"] = meta
    r.snapshot_json = snap
    db.commit()
    return _review_out(db, r, p)
