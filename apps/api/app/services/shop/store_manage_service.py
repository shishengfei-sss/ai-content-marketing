"""A17 店铺管理：列表、新建、开业/暂停/恢复。对照 #a17 · #a17a–d。"""

from __future__ import annotations

import csv
import io
import re
import uuid
from calendar import monthrange
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.shop import (
    ShopMerchantAccount,
    ShopOrder,
    ShopProduct,
    ShopStore,
    ShopStoreMembership,
    ShopStoreSettings,
)
from app.services.shop.entitlement_service import UNLIMITED, get_merged_entitlements
from app.services.shop.product_service import ensure_default_shop
from app.schemas.shop_platform import ShopExportTaskOut, StoreExportRequest

STATUS_LABELS = {
    "draft": "草稿",
    "active": "营业",
    "paused": "已暂停",
    "closed": "已关闭",
}
TAB_STATUS = {
    "draft": "draft",
    "active": "active",
    "paused": "paused",
    "pending_open": "draft",  # 待开业 = draft
}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,29}$")


# 顶栏「· 管理员」等展示名。对照 #a01 顶栏原文（非表单栏位）。
_HEADER_ROLE_LABEL = {
    "admin": "管理员",
    "shop_admin": "管理员",
    "shop_content": "内容运营",
    "shop_support": "客服",
    "shop_clerk": "店员",
}


def list_store_options(db: Session, ctx: TenantContext) -> dict:
    """A01 顶栏当前店铺下拉。对照 #a01-select-spec · C13。"""
    merchant = (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, ctx.tenant_id))
        .first()
    )
    role = ctx.membership.role if ctx.membership else None
    role_code = role.code if role else ""
    role_label = _HEADER_ROLE_LABEL.get(role_code) or (role.name if role else None)
    if not merchant:
        return {
            "items": [],
            "plan_label": None,
            "role_label": role_label,
            "store_scope": "all",
        }

    store_scope = "all"
    shop_ids: list[UUID] | None = None
    if role_code == "shop_clerk":
        store_scope = "selected"
        shop_ids = [
            r.shop_id
            for r in db.query(ShopStoreMembership)
            .filter(
                uuid_eq(ShopStoreMembership.tenant_id, ctx.tenant_id),
                uuid_eq(ShopStoreMembership.user_id, ctx.user.id),
            )
            .all()
        ]
        if not shop_ids:
            return {
                "items": [],
                "plan_label": merchant.plan_label or "免费版",
                "role_label": role_label,
                "store_scope": store_scope,
            }

    query = db.query(ShopStore).filter(
        uuid_eq(ShopStore.tenant_id, ctx.tenant_id),
        ShopStore.status != "closed",
    )
    if shop_ids is not None:
        query = query.filter(ShopStore.id.in_(shop_ids))
    rows = query.order_by(ShopStore.created_at.asc()).all()
    return {
        "items": [
            {"id": str(r.id), "name": r.name, "status": r.status, "slug": r.slug}
            for r in rows
        ],
        "plan_label": merchant.plan_label or "免费版",
        "role_label": role_label,
        "store_scope": store_scope,
    }


def _merchant(db: Session, tenant_id: UUID) -> ShopMerchantAccount:
    m = (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id))
        .first()
    )
    if not m:
        raise HTTPException(status_code=404, detail="商家未开通商城")
    return m


def _assert_merchant_active(m: ShopMerchantAccount) -> None:
    if m.status == "closed":
        raise HTTPException(status_code=422, detail="商家已清退")
    if m.status == "suspended":
        raise HTTPException(status_code=422, detail="商家已暂停")


def count_used_slots(db: Session, tenant_id: UUID) -> int:
    return (
        db.query(func.count(ShopStore.id))
        .filter(uuid_eq(ShopStore.tenant_id, tenant_id), ShopStore.status != "closed")
        .scalar()
        or 0
    )


def get_max_shops(db: Session, tenant_id: UUID) -> int | None:
    """None = unlimited。"""
    merged = get_merged_entitlements(db, tenant_id)
    val = (merged.get("quotas") or {}).get("quota.max_shops")
    if val == UNLIMITED or val == "unlimited":
        return None
    if isinstance(val, int):
        return val
    m = _merchant(db, tenant_id)
    if m.store_quota is None and val is None:
        # 无套餐快照时回落 merchant.store_quota；仍无则 1
        return 1
    if m.store_quota is None:
        return None
    return int(m.store_quota)


def quota_block(db: Session, tenant_id: UUID) -> dict:
    used = count_used_slots(db, tenant_id)
    mx = get_max_shops(db, tenant_id)
    return {
        "used": used,
        "max": mx,
        "source": "merged_entitlements",
        "at_limit": mx is not None and used >= mx,
    }


def _month_bounds_utc() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    last = monthrange(now.year, now.month)[1]
    end = datetime(now.year, now.month, last, 23, 59, 59, tzinfo=timezone.utc)
    return start, end


def _product_counts(db: Session, shop_ids: list[UUID]) -> dict[UUID, int]:
    if not shop_ids:
        return {}
    rows = (
        db.query(ShopProduct.shop_id, func.count(ShopProduct.id))
        .filter(
            ShopProduct.shop_id.in_(shop_ids),
            ShopProduct.deleted_at.is_(None),
        )
        .group_by(ShopProduct.shop_id)
        .all()
    )
    return {sid: int(c) for sid, c in rows}


def _month_gmv(db: Session, shop_ids: list[UUID]) -> dict[UUID, int]:
    if not shop_ids:
        return {}
    start, end = _month_bounds_utc()
    rows = (
        db.query(
            ShopOrder.shop_id,
            func.coalesce(
                func.sum(func.coalesce(ShopOrder.paid_amount_cents, ShopOrder.amount_cents)),
                0,
            ),
        )
        .filter(
            ShopOrder.shop_id.in_(shop_ids),
            ShopOrder.paid_at.isnot(None),
            ShopOrder.paid_at >= start,
            ShopOrder.paid_at <= end,
        )
        .group_by(ShopOrder.shop_id)
        .all()
    )
    return {sid: int(c or 0) for sid, c in rows}


def _on_sale_count(db: Session, shop_id: UUID) -> int:
    return (
        db.query(func.count(ShopProduct.id))
        .filter(
            uuid_eq(ShopProduct.shop_id, shop_id),
            ShopProduct.status == "on_sale",
            ShopProduct.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )


def _a19_ready(db: Session, shop: ShopStore) -> bool:
    """开业闸：A19 必填 — 店铺名称（对外）2–100 字。"""
    name = (shop.name or "").strip()
    return 2 <= len(name) <= 100


def _store_out(
    shop: ShopStore,
    *,
    product_count: int = 0,
    month_gmv_cents: int = 0,
    on_sale_count: int | None = None,
    a19_ready: bool | None = None,
) -> dict:
    return {
        "id": shop.id,
        "name": shop.name or "",
        "slug": shop.slug or "",
        "status": shop.status,
        "status_label": STATUS_LABELS.get(shop.status, shop.status),
        "logo_url": shop.logo_url,
        "product_count": product_count,
        "month_gmv_cents": month_gmv_cents,
        "on_sale_count": on_sale_count,
        "a19_ready": a19_ready,
        "created_at": shop.created_at,
        "updated_at": shop.updated_at,
    }


def status_counts(db: Session, tenant_id: UUID) -> dict:
    rows = (
        db.query(ShopStore.status, func.count(ShopStore.id))
        .filter(uuid_eq(ShopStore.tenant_id, tenant_id))
        .group_by(ShopStore.status)
        .all()
    )
    by = {s: int(c) for s, c in rows}
    draft = by.get("draft", 0)
    active = by.get("active", 0)
    paused = by.get("paused", 0)
    closed = by.get("closed", 0)
    return {
        "all": draft + active + paused,  # 默认不含 closed
        "draft": draft,
        "active": active,
        "paused": paused,
        "closed": closed,
    }


def list_stores(
    db: Session,
    ctx: TenantContext,
    *,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    tab: str | None = None,
    status: str | None = None,
    product_count_min: int | None = None,
    product_count_max: int | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    sort: str | None = None,
    include_closed: bool = False,
) -> dict:
    merchant = _merchant(db, ctx.tenant_id)
    ensure_default_shop(db, ctx.tenant_id, merchant)
    db.commit()

    query = db.query(ShopStore).filter(uuid_eq(ShopStore.tenant_id, ctx.tenant_id))
    if status:
        query = query.filter(ShopStore.status == status)
    elif tab in ("draft", "pending_open"):
        query = query.filter(ShopStore.status == "draft")
    elif tab == "active":
        query = query.filter(ShopStore.status == "active")
    elif tab == "paused":
        query = query.filter(ShopStore.status == "paused")
    elif not include_closed:
        query = query.filter(ShopStore.status != "closed")

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(ShopStore.name.ilike(like), ShopStore.slug.ilike(like)))

    if created_from:
        query = query.filter(ShopStore.created_at >= created_from)
    if created_to:
        query = query.filter(ShopStore.created_at <= created_to)

    rows = query.order_by(ShopStore.created_at.desc()).all()
    ids = [r.id for r in rows]
    pcounts = _product_counts(db, ids)
    gmvs = _month_gmv(db, ids)

    filtered: list[ShopStore] = []
    for r in rows:
        pc = pcounts.get(r.id, 0)
        if product_count_min is not None and pc < product_count_min:
            continue
        if product_count_max is not None and pc > product_count_max:
            continue
        filtered.append(r)

    # 排序
    sort_key = (sort or "").strip()
    reverse = sort_key.startswith("-")
    key = sort_key.lstrip("-") or "created_at"

    def sort_val(s: ShopStore):
        if key == "name":
            return (s.name or "").lower()
        if key == "product_count":
            return pcounts.get(s.id, 0)
        if key == "month_gmv":
            return gmvs.get(s.id, 0)
        return s.created_at or datetime.min.replace(tzinfo=timezone.utc)

    filtered.sort(key=sort_val, reverse=reverse if key != "created_at" else (reverse or True))
    if key == "created_at" and not sort_key:
        filtered.sort(key=lambda s: s.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    total = len(filtered)
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    start = (page - 1) * page_size
    page_rows = filtered[start : start + page_size]

    items = [
        _store_out(
            r,
            product_count=pcounts.get(r.id, 0),
            month_gmv_cents=gmvs.get(r.id, 0),
            on_sale_count=_on_sale_count(db, r.id) if r.status == "draft" else None,
            a19_ready=_a19_ready(db, r) if r.status == "draft" else None,
        )
        for r in page_rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "quota": quota_block(db, ctx.tenant_id),
        "status_counts": status_counts(db, ctx.tenant_id),
    }


def export_stores_csv(
    db: Session,
    ctx: TenantContext,
    *,
    q: str | None = None,
    tab: str | None = None,
    status: str | None = None,
    product_count_min: int | None = None,
    product_count_max: int | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    sort: str | None = None,
    include_closed: bool = False,
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    data = list_stores(
        db,
        ctx,
        page=1,
        page_size=5000,
        q=q,
        tab=tab,
        status=status,
        product_count_min=product_count_min,
        product_count_max=product_count_max,
        created_from=created_from,
        created_to=created_to,
        sort=sort,
        include_closed=include_closed,
    )
    total = int(data.get("total") or 0)
    if raise_too_many and total > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    default_headers = ["店铺名", "店铺短码", "商品数", "本月GMV分", "创建时间", "状态"]
    col_map = {
        "name": ["店铺名"],
        "slug": ["店铺短码"],
        "product_count": ["商品数"],
        "month_gmv": ["本月GMV分"],
        "created_at": ["创建时间"],
        "status": ["状态"],
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
    for it in data["items"]:
        values = {
            "店铺名": it["name"],
            "店铺短码": it["slug"],
            "商品数": it["product_count"],
            "本月GMV分": it["month_gmv_cents"],
            "创建时间": it["created_at"],
            "状态": it["status_label"],
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_store_export_task(
    db: Session, ctx: TenantContext, body: StoreExportRequest | None = None
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or StoreExportRequest()
    filters = {
        "q": body.q,
        "tab": body.tab,
        "status": body.status,
        "product_count_min": body.product_count_min,
        "product_count_max": body.product_count_max,
        "created_from": body.created_from,
        "created_to": body.created_to,
        "sort": body.sort,
        "include_closed": body.include_closed,
        "columns": body.columns,
    }
    csv_text = export_stores_csv(
        db,
        ctx,
        q=body.q,
        tab=body.tab,
        status=body.status,
        product_count_min=body.product_count_min,
        product_count_max=body.product_count_max,
        created_from=body.created_from,
        created_to=body.created_to,
        sort=body.sort,
        include_closed=body.include_closed,
        columns=body.columns,
        raise_too_many=True,
    )
    return export_task_service.persist_csv_task(
        db,
        ctx,
        resource="stores",
        file_name="shop-stores.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_store_export_task(db: Session, ctx: TenantContext, task_id: UUID) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task(db, ctx, task_id, "stores")


def read_store_export_file(db: Session, ctx: TenantContext, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file(db, ctx, task_id, "stores")


def create_store(
    db: Session,
    ctx: TenantContext,
    *,
    name: str,
    slug: str,
    intro: str | None = None,
) -> dict:
    merchant = _merchant(db, ctx.tenant_id)
    _assert_merchant_active(merchant)

    text = (name or "").strip()
    if len(text) < 2 or len(text) > 30:
        raise HTTPException(status_code=422, detail="店铺名称须为 2–30 字")
    code = (slug or "").strip().lower()
    if not SLUG_RE.match(code):
        raise HTTPException(status_code=422, detail="店铺短码须为 2–30 位小写字母/数字/下划线/中划线")

    exists = (
        db.query(ShopStore)
        .filter(uuid_eq(ShopStore.tenant_id, ctx.tenant_id), ShopStore.slug == code)
        .first()
    )
    if exists:
        raise HTTPException(status_code=422, detail="店铺短码已被占用")

    q = quota_block(db, ctx.tenant_id)
    if q["at_limit"]:
        raise HTTPException(status_code=422, detail="已达套餐店铺上限，请升级")

    shop = ShopStore(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        merchant_id=merchant.id,
        name=text,
        slug=code,
        status="draft",
    )
    db.add(shop)
    db.flush()
    settings = ShopStoreSettings(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        shop_id=shop.id,
        intro=(intro or "").strip() or None,
        theme_color="#1677ff",
        close_order_minutes=30,
        default_refund_policy="before_fulfill",
    )
    db.add(settings)
    db.commit()
    db.refresh(shop)
    return _store_out(shop, product_count=0, month_gmv_cents=0, on_sale_count=0, a19_ready=_a19_ready(db, shop))


def _get_owned(db: Session, ctx: TenantContext, store_id: UUID) -> ShopStore:
    shop = (
        db.query(ShopStore)
        .filter(uuid_eq(ShopStore.id, store_id), uuid_eq(ShopStore.tenant_id, ctx.tenant_id))
        .first()
    )
    if not shop:
        raise HTTPException(status_code=404, detail="店铺不存在")
    return shop


def open_store(db: Session, ctx: TenantContext, store_id: UUID) -> dict:
    merchant = _merchant(db, ctx.tenant_id)
    _assert_merchant_active(merchant)
    shop = _get_owned(db, ctx, store_id)
    if shop.status != "draft":
        raise HTTPException(status_code=422, detail="仅草稿可开业")
    if not _a19_ready(db, shop):
        raise HTTPException(status_code=422, detail="请先完善单店设置")
    if _on_sale_count(db, shop.id) < 1:
        raise HTTPException(status_code=422, detail="须至少 1 个在售商品")
    shop.status = "active"
    db.commit()
    db.refresh(shop)
    return _store_out(
        shop,
        product_count=_product_counts(db, [shop.id]).get(shop.id, 0),
        month_gmv_cents=_month_gmv(db, [shop.id]).get(shop.id, 0),
    )


def pause_store(db: Session, ctx: TenantContext, store_id: UUID) -> dict:
    merchant = _merchant(db, ctx.tenant_id)
    _assert_merchant_active(merchant)
    shop = _get_owned(db, ctx, store_id)
    if shop.status != "active":
        raise HTTPException(status_code=422, detail="仅营业中可暂停")
    shop.status = "paused"
    db.commit()
    db.refresh(shop)
    return _store_out(
        shop,
        product_count=_product_counts(db, [shop.id]).get(shop.id, 0),
        month_gmv_cents=_month_gmv(db, [shop.id]).get(shop.id, 0),
    )


def resume_store(db: Session, ctx: TenantContext, store_id: UUID) -> dict:
    merchant = _merchant(db, ctx.tenant_id)
    if merchant.status == "suspended":
        raise HTTPException(status_code=422, detail="商家已暂停，请联系平台")
    _assert_merchant_active(merchant)
    shop = _get_owned(db, ctx, store_id)
    if shop.status != "paused":
        raise HTTPException(status_code=422, detail="仅已暂停可恢复")
    shop.status = "active"
    db.commit()
    db.refresh(shop)
    return _store_out(
        shop,
        product_count=_product_counts(db, [shop.id]).get(shop.id, 0),
        month_gmv_cents=_month_gmv(db, [shop.id]).get(shop.id, 0),
    )


def open_readiness(db: Session, ctx: TenantContext, store_id: UUID) -> dict:
    shop = _get_owned(db, ctx, store_id)
    on_sale = _on_sale_count(db, shop.id)
    ready = _a19_ready(db, shop)
    return {
        "shop_id": shop.id,
        "status": shop.status,
        "a19_ready": ready,
        "on_sale_count": on_sale,
        "can_open": shop.status == "draft" and ready and on_sale >= 1,
    }
