"""A07 服务定义与可预约时段。对照 PRD #a07 · #a07-edit · §8.8.2。"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.shop import (
    ShopBuyer,
    ShopBooking,
    ShopEntitlement,
    ShopMerchantAccount,
    ShopProduct,
    ShopServiceOffer,
    ShopServiceSlot,
    ShopStore,
)
from app.schemas.shop_platform import (
    BookingOut,
    MpServiceSlotsResponse,
    ServiceOfferCreateRequest,
    ServiceOfferExportRequest,
    ServiceOfferOut,
    ServiceOfferPatchRequest,
    ServiceSlotBatchPreviewOut,
    ServiceSlotBatchRequest,
    ServiceSlotListResponse,
    ServiceSlotOut,
    ShopExportTaskOut,
)
from app.services.shop.product_service import ensure_default_shop

TZ_CN = timezone(timedelta(hours=8))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _merchant(db: Session, tenant_id: UUID) -> ShopMerchantAccount:
    m = db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    if not m:
        raise HTTPException(status_code=404, detail="商家未入驻")
    if m.status in ("closed", "suspended"):
        raise HTTPException(status_code=422, detail="商家不可用")
    return m


def _mask_mobile(mobile: str | None) -> str | None:
    if not mobile or len(mobile) < 7:
        return mobile
    return f"{mobile[:3]}****{mobile[-4:]}"


def _ref_count(db: Session, offer_id: UUID) -> int:
    return (
        db.query(ShopProduct)
        .filter(
            ShopProduct.ref_type == "service_offer",
            uuid_eq(ShopProduct.ref_id, offer_id),
            ShopProduct.deleted_at.is_(None),
        )
        .count()
    )


def _open_slot_count(db: Session, offer_id: UUID) -> int:
    now = _now()
    return (
        db.query(ShopServiceSlot)
        .filter(
            uuid_eq(ShopServiceSlot.service_offer_id, offer_id),
            ShopServiceSlot.status == "open",
            ShopServiceSlot.start_at > now,
        )
        .count()
    )


def _offer_out(db: Session, o: ShopServiceOffer) -> ServiceOfferOut:
    return ServiceOfferOut(
        id=o.id,
        tenant_id=o.tenant_id,
        shop_id=o.shop_id,
        title=o.title,
        mode=o.mode,
        status=o.status,
        total_times=o.total_times,
        valid_days=o.valid_days,
        duration_minutes=o.duration_minutes,
        ref_product_count=_ref_count(db, o.id),
        open_slot_count=_open_slot_count(db, o.id) if o.mode == "booking" else 0,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )


def _slot_out(s: ShopServiceSlot, *, selectable: bool | None = None) -> ServiceSlotOut:
    sel = selectable
    if sel is None:
        start = _aware(s.start_at) or _now()
        sel = s.status == "open" and s.booked_count < s.capacity and start > _now()
    return ServiceSlotOut(
        id=s.id,
        service_offer_id=s.service_offer_id,
        start_at=_aware(s.start_at) or s.start_at,
        end_at=_aware(s.end_at) or s.end_at,
        capacity=s.capacity,
        booked_count=s.booked_count,
        status=s.status,
        selectable=bool(sel),
    )


def _get_owned(db: Session, tenant_id: UUID, offer_id: UUID) -> ShopServiceOffer:
    o = (
        db.query(ShopServiceOffer)
        .filter(
            uuid_eq(ShopServiceOffer.id, offer_id),
            uuid_eq(ShopServiceOffer.tenant_id, tenant_id),
            ShopServiceOffer.deleted_at.is_(None),
        )
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="服务不存在")
    return o


def create_offer(db: Session, ctx: TenantContext, body: ServiceOfferCreateRequest) -> ServiceOfferOut:
    merchant = _merchant(db, ctx.tenant_id)
    store = (
        db.query(ShopStore).filter(uuid_eq(ShopStore.id, body.shop_id)).first()
        if body.shop_id
        else ensure_default_shop(db, ctx.tenant_id, merchant)
    )
    if not store or store.tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=404, detail="店铺不存在")
    if body.mode == "times_card" and not body.total_times:
        raise HTTPException(status_code=422, detail="次数卡须填写次数")
    o = ShopServiceOffer(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        shop_id=store.id,
        title=body.title.strip(),
        mode=body.mode,
        status="draft",
        total_times=body.total_times if body.mode == "times_card" else None,
        valid_days=body.valid_days if body.mode == "times_card" else body.valid_days,
        duration_minutes=body.duration_minutes,
        created_by=ctx.user.id,
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return _offer_out(db, o)


def list_offers(
    db: Session,
    ctx: TenantContext,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    mode: str | None = None,
    q: str | None = None,
    shop_id: UUID | None = None,
) -> tuple[list[ServiceOfferOut], int, dict[str, int]]:
    _merchant(db, ctx.tenant_id)
    base = db.query(ShopServiceOffer).filter(
        uuid_eq(ShopServiceOffer.tenant_id, ctx.tenant_id),
        ShopServiceOffer.deleted_at.is_(None),
    )
    if shop_id:
        base = base.filter(uuid_eq(ShopServiceOffer.shop_id, shop_id))
    counts = {
        "all": base.count(),
        "draft": base.filter(ShopServiceOffer.status == "draft").count(),
        "published": base.filter(ShopServiceOffer.status == "published").count(),
        "off_sale": base.filter(ShopServiceOffer.status == "off_sale").count(),
    }
    query = base
    if status:
        query = query.filter(ShopServiceOffer.status == status)
    if mode:
        query = query.filter(ShopServiceOffer.mode == mode)
    if q:
        query = query.filter(ShopServiceOffer.title.contains(q.strip()))
    total = query.count()
    rows = (
        query.order_by(ShopServiceOffer.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [_offer_out(db, r) for r in rows], total, counts


_OFFER_STATUS_ZH = {"draft": "草稿", "published": "已发布", "off_sale": "已下架"}
_OFFER_MODE_ZH = {"booking": "预约", "times_card": "次数卡"}


def export_offers_csv(
    db: Session,
    ctx: TenantContext,
    *,
    status: str | None = None,
    mode: str | None = None,
    q: str | None = None,
    shop_id: UUID | None = None,
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    import csv
    import io

    items, total, _ = list_offers(
        db, ctx, page=1, page_size=5000, status=status, mode=mode, q=q, shop_id=shop_id
    )
    if raise_too_many and total > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    default_headers = ["标题", "模式", "引用商品", "状态", "更新时间"]
    col_map = {
        "title": ["标题"],
        "mode": ["模式"],
        "ref_product_count": ["引用商品"],
        "status": ["状态"],
        "updated_at": ["更新时间"],
        "open_slot_count": ["开放时段"],
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
    for i in items:
        mode_zh = _OFFER_MODE_ZH.get(i.mode, i.mode or "")
        if i.mode == "times_card" and i.total_times:
            mode_zh = f"{mode_zh} · {i.total_times}次"
        values = {
            "标题": i.title or "",
            "模式": mode_zh,
            "引用商品": i.ref_product_count,
            "状态": _OFFER_STATUS_ZH.get(i.status, i.status),
            "更新时间": str(i.updated_at or ""),
            "开放时段": i.open_slot_count,
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_offer_export_task(
    db: Session, ctx: TenantContext, body: ServiceOfferExportRequest | None = None
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or ServiceOfferExportRequest()
    filters = {
        "shop_id": str(body.shop_id) if body.shop_id else None,
        "status": body.status,
        "mode": body.mode,
        "q": body.q,
        "columns": body.columns,
    }
    csv_text = export_offers_csv(
        db,
        ctx,
        status=body.status,
        mode=body.mode,
        q=body.q,
        shop_id=body.shop_id,
        columns=body.columns,
        raise_too_many=True,
    )
    return export_task_service.persist_csv_task(
        db,
        ctx,
        resource="service_offers",
        file_name="shop-service-offers.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_offer_export_task(db: Session, ctx: TenantContext, task_id: UUID) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task(db, ctx, task_id, "service_offers")


def read_offer_export_file(db: Session, ctx: TenantContext, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file(db, ctx, task_id, "service_offers")


def get_offer(db: Session, ctx: TenantContext, offer_id: UUID) -> ServiceOfferOut:
    return _offer_out(db, _get_owned(db, ctx.tenant_id, offer_id))


def patch_offer(
    db: Session, ctx: TenantContext, offer_id: UUID, body: ServiceOfferPatchRequest
) -> ServiceOfferOut:
    o = _get_owned(db, ctx.tenant_id, offer_id)
    if o.status == "off_sale":
        raise HTTPException(status_code=422, detail="已下架不可编辑")
    data = body.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        o.title = data["title"].strip()
        if not o.title:
            raise HTTPException(status_code=422, detail="请填写标题")
    if "mode" in data and data["mode"] is not None:
        o.mode = data["mode"]
    if "duration_minutes" in data and data["duration_minutes"] is not None:
        o.duration_minutes = data["duration_minutes"]
    if o.mode == "times_card":
        if "total_times" in data:
            o.total_times = data["total_times"]
        if "valid_days" in data:
            o.valid_days = data["valid_days"]
        if not o.total_times:
            raise HTTPException(status_code=422, detail="次数卡须填写次数")
    else:
        if "total_times" in data:
            o.total_times = None
    db.commit()
    db.refresh(o)
    return _offer_out(db, o)


def publish_offer(db: Session, ctx: TenantContext, offer_id: UUID) -> ServiceOfferOut:
    o = _get_owned(db, ctx.tenant_id, offer_id)
    if o.status != "draft":
        raise HTTPException(status_code=422, detail="仅草稿可发布")
    if not (o.title or "").strip():
        raise HTTPException(status_code=422, detail="请填写标题")
    if o.mode == "booking":
        if _open_slot_count(db, o.id) < 1:
            raise HTTPException(status_code=422, detail="请配置时段")
    elif o.mode == "times_card":
        if not o.total_times or not o.valid_days:
            raise HTTPException(status_code=422, detail="请填写次数与有效期")
    o.status = "published"
    db.commit()
    db.refresh(o)
    return _offer_out(db, o)


def off_sale_offer(db: Session, ctx: TenantContext, offer_id: UUID) -> ServiceOfferOut:
    o = _get_owned(db, ctx.tenant_id, offer_id)
    if o.status != "published":
        raise HTTPException(status_code=422, detail="仅已发布可下架")
    o.status = "off_sale"
    db.commit()
    db.refresh(o)
    return _offer_out(db, o)


def delete_offer(db: Session, ctx: TenantContext, offer_id: UUID) -> dict:
    o = _get_owned(db, ctx.tenant_id, offer_id)
    if o.status != "draft":
        raise HTTPException(status_code=422, detail="仅草稿可删")
    if _ref_count(db, o.id) > 0:
        raise HTTPException(status_code=422, detail="存在商品引用不可删")
    o.deleted_at = _now()
    db.commit()
    return {"ok": True}


def list_slots_merchant(
    db: Session,
    ctx: TenantContext,
    offer_id: UUID,
    *,
    status: str | None = None,
    view: str | None = None,
) -> tuple[list[ServiceSlotOut], int]:
    o = _get_owned(db, ctx.tenant_id, offer_id)
    q = db.query(ShopServiceSlot).filter(uuid_eq(ShopServiceSlot.service_offer_id, o.id))
    if status:
        q = q.filter(ShopServiceSlot.status == status)
    now = _now()
    if view == "upcoming":
        q = q.filter(ShopServiceSlot.start_at > now)
    elif view == "past":
        q = q.filter(ShopServiceSlot.end_at <= now)
    rows = q.order_by(ShopServiceSlot.start_at.asc()).all()
    return [_slot_out(s) for s in rows], len(rows)


def _parse_hm(s: str) -> time:
    hh, mm = s.split(":")
    return time(hour=int(hh), minute=int(mm))


def _iter_batch_candidates(
    offer: ShopServiceOffer, body: ServiceSlotBatchRequest
) -> tuple[list[tuple[datetime, datetime]], int, int]:
    if body.date_to < body.date_from:
        raise HTTPException(status_code=422, detail="日期范围无效")
    if (body.date_to - body.date_from).days > 90:
        raise HTTPException(status_code=422, detail="日期范围不可超过 90 天")
    windows = []
    for w in body.daily_windows:
        st, et = _parse_hm(w.start), _parse_hm(w.end)
        if et <= st:
            raise HTTPException(status_code=422, detail="开始时间须早于结束时间")
        windows.append((st, et))
    # 同行不重叠
    sorted_w = sorted(windows, key=lambda x: x[0])
    for i in range(1, len(sorted_w)):
        if sorted_w[i][0] < sorted_w[i - 1][1]:
            raise HTTPException(status_code=422, detail="每日时段不可重叠")

    skipped_weekend = 0
    candidates: list[tuple[datetime, datetime]] = []
    d = body.date_from
    while d <= body.date_to:
        if body.skip_weekends and d.weekday() >= 5:
            skipped_weekend += 1
            d += timedelta(days=1)
            continue
        for st, et in windows:
            # 以东八区墙钟解释，落库 UTC（SQLite 会丢 offset）
            start_at = datetime.combine(d, st, tzinfo=TZ_CN).astimezone(timezone.utc)
            end_at = datetime.combine(d, et, tzinfo=TZ_CN).astimezone(timezone.utc)
            candidates.append((start_at, end_at))
        d += timedelta(days=1)
    return candidates, skipped_weekend, 0


def _filter_overlap(
    db: Session, offer_id: UUID, candidates: list[tuple[datetime, datetime]], skip_overlap: bool
) -> tuple[list[tuple[datetime, datetime]], int]:
    if not candidates:
        return [], 0
    existing = (
        db.query(ShopServiceSlot)
        .filter(
            uuid_eq(ShopServiceSlot.service_offer_id, offer_id),
            ShopServiceSlot.status != "closed",
        )
        .all()
    )
    kept: list[tuple[datetime, datetime]] = []
    skipped = 0
    for start_at, end_at in candidates:
        overlap = any(not (end_at <= e.start_at or start_at >= e.end_at) for e in existing)
        if overlap:
            if skip_overlap:
                skipped += 1
                continue
            raise HTTPException(status_code=422, detail="时段重叠且未勾选跳过")
        # 与本批已选也不重叠
        if any(not (end_at <= k[0] or start_at >= k[1]) for k in kept):
            if skip_overlap:
                skipped += 1
                continue
            raise HTTPException(status_code=422, detail="时段重叠且未勾选跳过")
        kept.append((start_at, end_at))
    return kept, skipped


def preview_batch_slots(
    db: Session, ctx: TenantContext, offer_id: UUID, body: ServiceSlotBatchRequest
) -> ServiceSlotBatchPreviewOut:
    o = _get_owned(db, ctx.tenant_id, offer_id)
    if o.status == "off_sale":
        raise HTTPException(status_code=422, detail="服务已下架")
    if o.mode != "booking":
        raise HTTPException(status_code=422, detail="次数卡无需时段")
    candidates, skipped_weekend, _ = _iter_batch_candidates(o, body)
    kept, skipped_overlap = _filter_overlap(db, o.id, candidates, body.skip_overlap)
    preview = [
        ServiceSlotOut(
            id=uuid.uuid4(),
            service_offer_id=o.id,
            start_at=s,
            end_at=e,
            capacity=body.capacity,
            booked_count=0,
            status="open",
            selectable=True,
        )
        for s, e in kept[:50]
    ]
    return ServiceSlotBatchPreviewOut(
        will_create=len(kept),
        skipped_weekend=skipped_weekend,
        skipped_overlap=skipped_overlap,
        preview=preview,
    )


def create_batch_slots(
    db: Session, ctx: TenantContext, offer_id: UUID, body: ServiceSlotBatchRequest
) -> ServiceSlotListResponse:
    preview = preview_batch_slots(db, ctx, offer_id, body)
    if preview.will_create < 1:
        raise HTTPException(status_code=422, detail="预览 0 条")
    o = _get_owned(db, ctx.tenant_id, offer_id)
    candidates, _, _ = _iter_batch_candidates(o, body)
    kept, _ = _filter_overlap(db, o.id, candidates, body.skip_overlap)
    created: list[ShopServiceSlot] = []
    for start_at, end_at in kept:
        slot = ShopServiceSlot(
            id=uuid.uuid4(),
            tenant_id=o.tenant_id,
            shop_id=o.shop_id,
            service_offer_id=o.id,
            start_at=start_at,
            end_at=end_at,
            capacity=body.capacity,
            booked_count=0,
            status="open",
        )
        db.add(slot)
        created.append(slot)
    db.commit()
    for s in created:
        db.refresh(s)
    return ServiceSlotListResponse(items=[_slot_out(s) for s in created], total=len(created))


def close_slot(db: Session, ctx: TenantContext, offer_id: UUID, slot_id: UUID) -> ServiceSlotOut:
    o = _get_owned(db, ctx.tenant_id, offer_id)
    if o.status == "off_sale":
        raise HTTPException(status_code=422, detail="服务已下架")
    slot = (
        db.query(ShopServiceSlot)
        .filter(
            uuid_eq(ShopServiceSlot.id, slot_id),
            uuid_eq(ShopServiceSlot.service_offer_id, o.id),
        )
        .first()
    )
    if not slot:
        raise HTTPException(status_code=404, detail="时段不存在")
    if slot.status not in ("open", "full"):
        raise HTTPException(status_code=422, detail="仅开放/已满可关闭")
    slot.status = "closed"
    bookings = (
        db.query(ShopBooking)
        .filter(uuid_eq(ShopBooking.slot_id, slot.id), ShopBooking.status == "booked")
        .all()
    )
    now = _now()
    for b in bookings:
        b.status = "cancelled"
        b.cancelled_at = now
        b.cancel_reason = "slot_closed"
    slot.booked_count = 0
    db.commit()
    db.refresh(slot)
    return _slot_out(slot)


def list_slot_bookings(
    db: Session, ctx: TenantContext, offer_id: UUID, slot_id: UUID
) -> list[BookingOut]:
    o = _get_owned(db, ctx.tenant_id, offer_id)
    slot = (
        db.query(ShopServiceSlot)
        .filter(
            uuid_eq(ShopServiceSlot.id, slot_id),
            uuid_eq(ShopServiceSlot.service_offer_id, o.id),
        )
        .first()
    )
    if not slot:
        raise HTTPException(status_code=404, detail="时段不存在")
    rows = (
        db.query(ShopBooking)
        .filter(uuid_eq(ShopBooking.slot_id, slot.id))
        .order_by(ShopBooking.created_at.asc())
        .all()
    )
    buyers = {
        b.id: b
        for b in db.query(ShopBuyer).filter(ShopBuyer.id.in_([r.buyer_id for r in rows] or [uuid.uuid4()])).all()
    }
    products = {
        p.id: p
        for p in db.query(ShopProduct)
        .filter(ShopProduct.id.in_([r.service_product_id for r in rows] or [uuid.uuid4()]))
        .all()
    }
    out: list[BookingOut] = []
    for r in rows:
        buyer = buyers.get(r.buyer_id)
        product = products.get(r.service_product_id)
        out.append(
            BookingOut(
                id=r.id,
                tenant_id=r.tenant_id,
                shop_id=r.shop_id,
                buyer_id=r.buyer_id,
                entitlement_id=r.entitlement_id,
                service_product_id=r.service_product_id,
                slot_id=r.slot_id,
                status=r.status,
                booked_date=r.booked_date,
                booked_time_slot=r.booked_time_slot,
                cancelled_at=r.cancelled_at,
                cancel_reason=r.cancel_reason,
                product_name=product.name if product else None,
                buyer_mobile_masked=_mask_mobile(buyer.mobile if buyer else None),
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )
    return out


def mp_list_slots(
    db: Session,
    buyer_tenant_id: UUID,
    offer_id: UUID,
    *,
    entitlement_id: UUID | None,
    date_from: date | None,
    date_to: date | None,
) -> MpServiceSlotsResponse:
    o = (
        db.query(ShopServiceOffer)
        .filter(
            uuid_eq(ShopServiceOffer.id, offer_id),
            uuid_eq(ShopServiceOffer.tenant_id, buyer_tenant_id),
            ShopServiceOffer.deleted_at.is_(None),
        )
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="服务不存在")

    remaining = None
    valid_until = None
    if entitlement_id:
        ent = (
            db.query(ShopEntitlement)
            .filter(
                uuid_eq(ShopEntitlement.id, entitlement_id),
                uuid_eq(ShopEntitlement.tenant_id, buyer_tenant_id),
            )
            .first()
        )
        if ent:
            remaining = ent.remaining_count
            if o.valid_days and ent.activated_at:
                base = ent.activated_at.astimezone(TZ_CN).date() if ent.activated_at.tzinfo else ent.activated_at.date()
                valid_until = base + timedelta(days=o.valid_days)

    if o.mode == "times_card":
        return MpServiceSlotsResponse(
            mode="times_card",
            slots=[],
            remaining_times=remaining,
            valid_until=valid_until,
            total_times=o.total_times,
            duration_minutes=o.duration_minutes,
        )

    now = _now()
    df = date_from or now.astimezone(TZ_CN).date()
    dt = date_to or (df + timedelta(days=14))
    start_bound = datetime.combine(df, time.min, tzinfo=TZ_CN)
    end_bound = datetime.combine(dt, time.max, tzinfo=TZ_CN)
    rows = (
        db.query(ShopServiceSlot)
        .filter(
            uuid_eq(ShopServiceSlot.service_offer_id, o.id),
            ShopServiceSlot.start_at >= start_bound,
            ShopServiceSlot.start_at <= end_bound,
            ShopServiceSlot.status.in_(("open", "full")),
        )
        .order_by(ShopServiceSlot.start_at.asc())
        .all()
    )
    # 服务下架：不可新约
    allow_new = o.status == "published"
    slots = []
    for s in rows:
        start = _aware(s.start_at) or now
        selectable = allow_new and s.status == "open" and s.booked_count < s.capacity and start > now
        slots.append(_slot_out(s, selectable=selectable))
    return MpServiceSlotsResponse(
        mode="booking",
        slots=slots,
        remaining_times=remaining,
        valid_until=valid_until,
        total_times=o.total_times,
        duration_minutes=o.duration_minutes,
    )


def try_occupy_slot(db: Session, slot_id: UUID) -> ShopServiceSlot:
    """条件更新防超卖；失败抛 409。"""
    slot = db.query(ShopServiceSlot).filter(uuid_eq(ShopServiceSlot.id, slot_id)).first()
    if not slot:
        raise HTTPException(status_code=404, detail="时段不存在")
    if slot.status == "closed":
        raise HTTPException(status_code=409, detail="时段已关闭")
    if slot.status == "full" or slot.booked_count >= slot.capacity:
        raise HTTPException(status_code=409, detail="时段已满")
    if (_aware(slot.start_at) or _now()) <= _now():
        raise HTTPException(status_code=409, detail="时段已过期")

    updated = (
        db.query(ShopServiceSlot)
        .filter(
            uuid_eq(ShopServiceSlot.id, slot_id),
            ShopServiceSlot.status == "open",
            ShopServiceSlot.booked_count < ShopServiceSlot.capacity,
        )
        .update(
            {ShopServiceSlot.booked_count: ShopServiceSlot.booked_count + 1},
            synchronize_session=False,
        )
    )
    if not updated:
        raise HTTPException(status_code=409, detail="时段已满")
    db.flush()
    slot = db.query(ShopServiceSlot).filter(uuid_eq(ShopServiceSlot.id, slot_id)).first()
    assert slot is not None
    if slot.booked_count >= slot.capacity:
        slot.status = "full"
        db.flush()
    return slot


def release_slot(db: Session, slot_id: UUID | None) -> None:
    if not slot_id:
        return
    slot = db.query(ShopServiceSlot).filter(uuid_eq(ShopServiceSlot.id, slot_id)).first()
    if not slot or slot.status == "closed":
        return
    if slot.booked_count > 0:
        slot.booked_count -= 1
    if slot.status == "full" and slot.booked_count < slot.capacity:
        slot.status = "open"
    db.flush()
