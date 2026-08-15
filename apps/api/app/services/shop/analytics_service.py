"""A01 交易看板。对照 PRD 01-管理端UI.html #a01 · §8.15.1。"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.shop import (
    ShopEntitlement,
    ShopInvoiceRequest,
    ShopMerchantAccount,
    ShopOrder,
    ShopProduct,
    ShopRefund,
    ShopStore,
)
from app.schemas.shop_platform import (
    AnalyticsResumeBanner,
    AnalyticsShareItem,
    AnalyticsStoreOption,
    AnalyticsSummaryOut,
    AnalyticsTrendPoint,
    AnalyticsTrendsOut,
    OrderListResponse,
)
from app.services.shop.entitlement_service import TZ_SH, now_sh
from app.services.shop import order_service

_RANGE_PRESETS = ("today", "7d", "30d", "custom")
_PAID_STATUSES = ("paid", "claim_pending", "refunding", "refunded")
_CAT_LABEL = {"course": "课", "digital": "资料", "service": "服务"}
_CH_LABEL = {"private": "微信", "public_douyin": "抖店"}
_PENDING_ORDER_STATUSES = ("pending_payment", "claim_pending", "refunding")


def parse_range(
    range_key: str | None,
    date_from: str | None,
    date_to: str | None,
) -> tuple[str, datetime, datetime]:
    key = (range_key or "today").strip().lower()
    if key not in _RANGE_PRESETS:
        raise HTTPException(status_code=422, detail="时间范围须为今日/近7/近30/自定义")
    now = now_sh()
    today = datetime.combine(now.date(), time.min, tzinfo=TZ_SH)
    tomorrow = today + timedelta(days=1)
    if key == "today":
        return key, today, tomorrow
    if key == "7d":
        return key, today - timedelta(days=6), tomorrow
    if key == "30d":
        return key, today - timedelta(days=29), tomorrow

    if not date_from or not date_to:
        raise HTTPException(status_code=422, detail="自定义须填写起止日期")
    try:
        start_d = datetime.strptime(date_from[:10], "%Y-%m-%d").date()
        end_d = datetime.strptime(date_to[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="日期格式须为 YYYY-MM-DD") from exc
    if end_d < start_d:
        raise HTTPException(status_code=422, detail="结束日期不可早于开始日期")
    if (end_d - start_d).days > 89:
        raise HTTPException(status_code=422, detail="自定义区间最长 90 天")
    start = datetime.combine(start_d, time.min, tzinfo=TZ_SH)
    end = datetime.combine(end_d + timedelta(days=1), time.min, tzinfo=TZ_SH)
    return key, start, end


def _shop_filter(query, shop_id: UUID | None, col):
    if shop_id:
        return query.filter(uuid_eq(col, shop_id))
    return query


def _gmv_expr():
    return func.coalesce(ShopOrder.paid_amount_cents, ShopOrder.amount_cents, 0)


def _paid_query(db: Session, tenant_id: UUID, shop_id: UUID | None, start: datetime, end: datetime):
    q = db.query(ShopOrder).filter(
        uuid_eq(ShopOrder.tenant_id, tenant_id),
        ShopOrder.paid_at.isnot(None),
        ShopOrder.paid_at >= start,
        ShopOrder.paid_at < end,
        ShopOrder.status.in_(_PAID_STATUSES),
    )
    return _shop_filter(q, shop_id, ShopOrder.shop_id)


def get_summary(
    db: Session,
    ctx: TenantContext,
    *,
    range_key: str | None,
    date_from: str | None,
    date_to: str | None,
    shop_id: UUID | None,
) -> AnalyticsSummaryOut:
    key, start, end = parse_range(range_key, date_from, date_to)
    tenant_id = ctx.tenant_id
    paid_base = _paid_query(db, tenant_id, shop_id, start, end)
    order_count = int(paid_base.count())
    gmv = int(
        _paid_query(db, tenant_id, shop_id, start, end)
        .with_entities(func.coalesce(func.sum(_gmv_expr()), 0))
        .scalar()
        or 0
    )

    pending_refunds = int(
        _shop_filter(
            db.query(func.count(ShopOrder.id)).filter(
                uuid_eq(ShopOrder.tenant_id, tenant_id),
                ShopOrder.status == "refunding",
            ),
            shop_id,
            ShopOrder.shop_id,
        ).scalar()
        or 0
    )
    processing_q = (
        db.query(func.count(ShopRefund.id))
        .join(ShopOrder, ShopOrder.id == ShopRefund.order_id)
        .filter(
            uuid_eq(ShopRefund.tenant_id, tenant_id),
            ShopRefund.status == "processing",
            ShopOrder.status != "refunding",
        )
    )
    processing_q = _shop_filter(processing_q, shop_id, ShopOrder.shop_id)
    pending_refunds += int(processing_q.scalar() or 0)

    pending_invoices = int(
        _shop_filter(
            db.query(func.count(ShopInvoiceRequest.id)).filter(
                uuid_eq(ShopInvoiceRequest.tenant_id, tenant_id),
                ShopInvoiceRequest.status.in_(("submitted", "pending")),
            ),
            shop_id,
            ShopInvoiceRequest.shop_id,
        ).scalar()
        or 0
    )
    pending_claims = int(
        _shop_filter(
            db.query(func.count(ShopOrder.id)).filter(
                uuid_eq(ShopOrder.tenant_id, tenant_id),
                ShopOrder.status == "claim_pending",
            ),
            shop_id,
            ShopOrder.shop_id,
        ).scalar()
        or 0
    )
    verify_q = (
        db.query(func.count(ShopEntitlement.id))
        .join(ShopProduct, ShopProduct.id == ShopEntitlement.product_id)
        .filter(
            uuid_eq(ShopEntitlement.tenant_id, tenant_id),
            ShopEntitlement.status == "active",
            ShopProduct.type == "service",
            ShopEntitlement.remaining_count.isnot(None),
            ShopEntitlement.remaining_count > 0,
        )
    )
    verify_q = _shop_filter(verify_q, shop_id, ShopEntitlement.shop_id)
    pending_verify = int(verify_q.scalar() or 0)
    off_sale = int(
        _shop_filter(
            db.query(func.count(ShopProduct.id)).filter(
                uuid_eq(ShopProduct.tenant_id, tenant_id),
                ShopProduct.status == "off_sale",
            ),
            shop_id,
            ShopProduct.shop_id,
        ).scalar()
        or 0
    )

    merchant = (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id))
        .first()
    )
    paused_q = db.query(func.count(ShopStore.id)).filter(
        uuid_eq(ShopStore.tenant_id, tenant_id),
        ShopStore.status == "paused",
    )
    paused_count = int(paused_q.scalar() or 0)
    pending_orders = int(
        db.query(func.count(ShopOrder.id))
        .filter(
            uuid_eq(ShopOrder.tenant_id, tenant_id),
            ShopOrder.status.in_(_PENDING_ORDER_STATUSES),
        )
        .scalar()
        or 0
    )
    resume = AnalyticsResumeBanner(
        show=bool(merchant and merchant.status == "active" and paused_count > 0),
        paused_store_count=paused_count,
        pending_order_count=pending_orders,
    )

    stores = (
        db.query(ShopStore)
        .filter(
            uuid_eq(ShopStore.tenant_id, tenant_id),
            ShopStore.status != "closed",
        )
        .order_by(ShopStore.created_at.asc())
        .all()
    )
    return AnalyticsSummaryOut(
        range=key,
        date_from=start.date().isoformat(),
        date_to=(end - timedelta(days=1)).date().isoformat(),
        shop_id=shop_id,
        gmv_cents=gmv,
        order_count=order_count,
        payment_conversion=None,
        pending_refunds=pending_refunds,
        pending_verify=pending_verify,
        pending_invoices=pending_invoices,
        pending_claims=pending_claims,
        off_sale_products=off_sale,
        resume=resume,
        stores=[AnalyticsStoreOption(id=s.id, name=s.name, status=s.status) for s in stores],
    )


def get_trends(
    db: Session,
    ctx: TenantContext,
    *,
    range_key: str | None,
    date_from: str | None,
    date_to: str | None,
    shop_id: UUID | None,
) -> AnalyticsTrendsOut:
    key, start, end = parse_range(range_key, date_from, date_to)
    rows = _paid_query(db, ctx.tenant_id, shop_id, start, end).all()

    by_day: dict[str, list[int]] = {}
    by_cat: dict[str, list[int]] = {}
    by_ch: dict[str, list[int]] = {}

    def _add(bucket: dict[str, list[int]], k: str, cents: int) -> None:
        cur = bucket.setdefault(k, [0, 0])
        cur[0] += cents
        cur[1] += 1

    for o in rows:
        paid_at = o.paid_at
        if paid_at.tzinfo is None:
            paid_at = paid_at.replace(tzinfo=TZ_SH)
        day = paid_at.astimezone(TZ_SH).date().isoformat()
        cents = int(o.paid_amount_cents if o.paid_amount_cents is not None else o.amount_cents or 0)
        _add(by_day, day, cents)
        _add(by_cat, o.type or "other", cents)
        src = o.source or "private"
        ch = src if src in _CH_LABEL else "other"
        _add(by_ch, ch, cents)

    daily: list[AnalyticsTrendPoint] = []
    cursor = start
    while cursor < end:
        d = cursor.date().isoformat()
        gmv, cnt = by_day.get(d, [0, 0])
        daily.append(AnalyticsTrendPoint(date=d, gmv_cents=int(gmv), order_count=int(cnt)))
        cursor += timedelta(days=1)

    def _shares(raw: dict[str, list[int]], labels: dict[str, str]) -> list[AnalyticsShareItem]:
        total = sum(v[0] for v in raw.values()) or 0
        items: list[AnalyticsShareItem] = []
        for k, (cents, cnt) in raw.items():
            items.append(
                AnalyticsShareItem(
                    key=k,
                    label=labels.get(k, "其它"),
                    amount_cents=int(cents),
                    count=int(cnt),
                    percent=round((cents / total) * 100, 1) if total else 0.0,
                )
            )
        items.sort(key=lambda x: x.amount_cents, reverse=True)
        return items

    return AnalyticsTrendsOut(
        range=key,
        date_from=start.date().isoformat(),
        date_to=(end - timedelta(days=1)).date().isoformat(),
        daily=daily,
        by_category=_shares(by_cat, _CAT_LABEL),
        by_channel=_shares(by_ch, {**_CH_LABEL, "other": "其它"}),
    )


def list_recent_orders(
    db: Session,
    ctx: TenantContext,
    *,
    shop_id: UUID | None,
    q: str | None,
    source: str | None,
    status_filter: str | None,
    page: int,
    page_size: int,
    sort_by: str | None,
    sort_dir: str | None,
) -> OrderListResponse:
    items, total, counts = order_service.list_merchant_orders(
        db,
        ctx,
        status_filter=status_filter,
        q=q,
        page=page,
        page_size=page_size,
        source=source,
        shop_id=shop_id,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return OrderListResponse(
        items=items, total=total, page=page, page_size=page_size, status_counts=counts
    )
