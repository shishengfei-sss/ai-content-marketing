"""M6：核销 / 预约 / 开票 / 学课进度。"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import String as SAString
from sqlalchemy import cast, or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import User
from app.models.shop import (
    ShopBooking,
    ShopBuyer,
    ShopEntitlement,
    ShopInvoiceRequest,
    ShopLessonProgress,
    ShopOrder,
    ShopProduct,
    ShopServiceSlot,
    ShopStore,
    ShopVerification,
)
from app.schemas.shop_platform import (
    BookingCancelRequest,
    BookingCreateRequest,
    BookingExportRequest,
    BookingOut,
    InvoiceCreateRequest,
    InvoiceExportRequest,
    InvoiceIssueRequest,
    ShopExportTaskOut,
    InvoiceOut,
    InvoiceRejectRequest,
    LessonProgressOut,
    LessonProgressUpsertRequest,
    VerificationExecuteRequest,
    VerificationExportRequest,
    VerificationLookupItem,
    VerificationLookupRequest,
    VerificationLookupResponse,
    VerificationOut,
)
from app.services.shop.buyer_service import mask_mobile
from app.services.shop.order_service import display_entitlement_status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _default_shop(db: Session, tenant_id: UUID) -> ShopStore:
    shop = (
        db.query(ShopStore)
        .filter(uuid_eq(ShopStore.tenant_id, tenant_id))
        .order_by(ShopStore.created_at.asc())
        .first()
    )
    if not shop:
        raise HTTPException(status_code=404, detail="店铺不存在")
    return shop


def _product_name(db: Session, product_id: UUID) -> tuple[str | None, str | None]:
    p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, product_id)).first()
    if not p:
        return None, None
    return p.name, p.type


def verification_no(verification_id: UUID | str) -> str:
    hexid = str(verification_id).replace("-", "")
    return "RD" + hexid[-6:].upper()


def _fmt_md_hm(dt: datetime | None) -> str:
    if not dt:
        return ""
    s = str(dt).replace("T", " ")
    # 08-05 15:30
    if len(s) >= 16:
        return s[5:16]
    return s[:16]


def _parse_created_bound(value: str | date | datetime | None, *, end: bool) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return _date_end_excl(value) if end else _date_start(value)
    raw = str(value).strip()
    try:
        d = date.fromisoformat(raw[:10])
        return _date_end_excl(d) if end else _date_start(d)
    except ValueError:
        return None


def _remaining_snapshots(
    db: Session, rows: list, ents: dict
) -> dict:
    """按权益倒推每次核销的 remaining_before / remaining_after。"""
    result: dict = {}
    if not rows:
        return result
    ent_ids = {r.entitlement_id for r in rows}
    all_vs = (
        db.query(ShopVerification)
        .filter(
            ShopVerification.entitlement_id.in_(list(ent_ids) or [uuid.uuid4()]),
            ShopVerification.status == "success",
        )
        .all()
    )
    by_ent: dict = {}
    for v in all_vs:
        by_ent.setdefault(v.entitlement_id, []).append(v)
    for eid, vs in by_ent.items():
        ent = ents.get(eid)
        remaining = ent.remaining_count if ent is not None else None
        vs_sorted = sorted(
            vs,
            key=lambda x: x.created_at or datetime(1970, 1, 1, tzinfo=timezone.utc),
        )
        if remaining is None:
            for v in vs_sorted:
                result[v.id] = (None, None)
            continue
        after = int(remaining)
        for v in reversed(vs_sorted):
            before = after + int(v.deducted_count or 0)
            result[v.id] = (before, after)
            after = before
    return result


def _verification_out(
    db: Session,
    v: ShopVerification,
    ent: ShopEntitlement | None = None,
    *,
    buyer: ShopBuyer | None = None,
    product: ShopProduct | None = None,
    booking: ShopBooking | None = None,
    operator: User | None = None,
    remaining_before: int | None = None,
    remaining_after: int | None = None,
) -> VerificationOut:
    if buyer is None and v.buyer_id:
        buyer = db.query(ShopBuyer).filter(uuid_eq(ShopBuyer.id, v.buyer_id)).first()
    if product is None and ent is not None:
        product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, ent.product_id)).first()
    if booking is None and v.booking_id:
        booking = db.query(ShopBooking).filter(uuid_eq(ShopBooking.id, v.booking_id)).first()
    if operator is None and v.operator_id:
        operator = db.query(User).filter(uuid_eq(User.id, v.operator_id)).first()
    slot = None
    if booking:
        slot = f"{booking.booked_date} {booking.booked_time_slot}"
    return VerificationOut(
        id=v.id,
        tenant_id=v.tenant_id,
        shop_id=v.shop_id,
        buyer_id=v.buyer_id,
        entitlement_id=v.entitlement_id,
        booking_id=v.booking_id,
        type=v.type,
        status=v.status,
        operator_id=v.operator_id,
        operator_name=(operator.display_name or operator.phone) if operator else None,
        verify_code=v.verify_code,
        idempotency_key=v.idempotency_key,
        deducted_count=v.deducted_count,
        remaining_count=ent.remaining_count if ent else None,
        remaining_before=remaining_before,
        remaining_after=remaining_after,
        verification_no=verification_no(v.id),
        entitlement_status=display_entitlement_status(ent),
        buyer_mobile_masked=mask_mobile(buyer.mobile) if buyer and buyer.mobile else None,
        product_name=product.name if product else None,
        booking_slot=slot,
        created_at=v.created_at,
    )


_BOOKING_STATUS_LABEL = {
    "booked": "待服务",
    "completed": "已完成",
    "cancelled": "已取消",
}


def booking_no_of(booking_id: UUID | str) -> str:
    hexid = str(booking_id).replace("-", "")
    return "BK" + hexid[-6:].upper()


def _booking_out(
    b: ShopBooking,
    product_name: str | None = None,
    *,
    shop_name: str | None = None,
    verify_code: str | None = None,
    order_id: UUID | None = None,
    order_no: str | None = None,
    offer_id: UUID | None = None,
    buyer_mobile_masked: str | None = None,
) -> BookingOut:
    show_code = verify_code if b.status == "booked" else None
    return BookingOut(
        id=b.id,
        tenant_id=b.tenant_id,
        shop_id=b.shop_id,
        buyer_id=b.buyer_id,
        entitlement_id=b.entitlement_id,
        service_product_id=b.service_product_id,
        slot_id=b.slot_id,
        status=b.status,
        booked_date=b.booked_date,
        booked_time_slot=b.booked_time_slot,
        cancelled_at=b.cancelled_at,
        cancel_reason=b.cancel_reason,
        product_name=product_name,
        buyer_mobile_masked=buyer_mobile_masked,
        created_at=b.created_at,
        updated_at=b.updated_at,
        booking_no=booking_no_of(b.id),
        status_label=_BOOKING_STATUS_LABEL.get(b.status, b.status),
        shop_name=shop_name,
        verify_code=show_code,
        order_id=order_id,
        order_no=order_no,
        offer_id=offer_id,
    )


def _pack_bookings(db: Session, rows: list[ShopBooking]) -> list[BookingOut]:
    if not rows:
        return []
    products = {
        p.id: p
        for p in db.query(ShopProduct)
        .filter(ShopProduct.id.in_([r.service_product_id for r in rows] or [uuid.uuid4()]))
        .all()
    }
    shops = {
        s.id: s
        for s in db.query(ShopStore)
        .filter(ShopStore.id.in_([r.shop_id for r in rows] or [uuid.uuid4()]))
        .all()
    }
    ents = {
        e.id: e
        for e in db.query(ShopEntitlement)
        .filter(ShopEntitlement.id.in_([r.entitlement_id for r in rows] or [uuid.uuid4()]))
        .all()
    }
    slots = {
        s.id: s
        for s in db.query(ShopServiceSlot)
        .filter(ShopServiceSlot.id.in_([r.slot_id for r in rows if r.slot_id] or [uuid.uuid4()]))
        .all()
    }
    order_ids = [e.order_id for e in ents.values() if e.order_id]
    orders = {
        o.id: o
        for o in db.query(ShopOrder).filter(ShopOrder.id.in_(order_ids or [uuid.uuid4()])).all()
    }
    buyers = {
        b.id: b
        for b in db.query(ShopBuyer)
        .filter(ShopBuyer.id.in_([r.buyer_id for r in rows] or [uuid.uuid4()]))
        .all()
    }
    out: list[BookingOut] = []
    for r in rows:
        ent = ents.get(r.entitlement_id)
        order = orders.get(ent.order_id) if ent and ent.order_id else None
        slot = slots.get(r.slot_id) if r.slot_id else None
        buyer = buyers.get(r.buyer_id)
        out.append(
            _booking_out(
                r,
                products.get(r.service_product_id).name if products.get(r.service_product_id) else None,
                shop_name=shops.get(r.shop_id).name if shops.get(r.shop_id) else None,
                verify_code=ent.verify_code if ent else None,
                order_id=ent.order_id if ent else None,
                order_no=order.order_no if order else None,
                offer_id=slot.service_offer_id if slot else None,
                buyer_mobile_masked=mask_mobile(buyer.mobile) if buyer and buyer.mobile else None,
            )
        )
    return out


def invoice_application_no(invoice_id: UUID | str) -> str:
    hexid = str(invoice_id).replace("-", "")
    return "INV" + hexid[-6:].upper()


def _date_start(d: date) -> datetime:
    return datetime.combine(d, time.min)


def _date_end_excl(d: date) -> datetime:
    return datetime.combine(d + timedelta(days=1), time.min)


def _operator_name(db: Session, operator_id) -> str | None:
    if not operator_id:
        return None
    u = db.query(User).filter(uuid_eq(User.id, operator_id)).first()
    if not u:
        return None
    return ((u.display_name or "").strip() or u.phone or "").strip() or None


def _invoice_out(
    inv: ShopInvoiceRequest,
    order: ShopOrder | None = None,
    *,
    operator_name: str | None = None,
) -> InvoiceOut:
    status = inv.status
    if status == "pending":
        status = "submitted"
    return InvoiceOut(
        id=inv.id,
        tenant_id=inv.tenant_id,
        shop_id=inv.shop_id,
        buyer_id=inv.buyer_id,
        order_id=inv.order_id,
        order_no=order.order_no if order else None,
        invoice_type=inv.invoice_type,
        title_type=inv.title_type,
        title=inv.title,
        tax_no=inv.tax_no,
        bank_name=inv.bank_name,
        bank_account=inv.bank_account,
        address=inv.address,
        phone=inv.phone,
        email=inv.email,
        amount_cents=inv.amount_cents,
        status=status,
        issued_at=inv.issued_at,
        invoice_no=inv.invoice_no,
        application_no=invoice_application_no(inv.id),
        invoice_url=inv.invoice_url,
        remark=getattr(inv, "remark", None),
        needs_red_flush=bool(inv.needs_red_flush),
        reject_reason=inv.reject_reason,
        operator_name=operator_name,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
    )


def _lesson_out(row: ShopLessonProgress) -> LessonProgressOut:
    return LessonProgressOut(
        id=row.id,
        tenant_id=row.tenant_id,
        buyer_id=row.buyer_id,
        entitlement_id=row.entitlement_id,
        course_id=row.course_id,
        lesson_id=row.lesson_id,
        position_sec=row.position_sec,
        progress_pct=row.progress_pct,
        last_learned_at=row.last_learned_at,
        updated_at=row.updated_at,
    )


def _lookup_item(
    db: Session, ent: ShopEntitlement, buyer: ShopBuyer | None, product: ShopProduct | None
) -> VerificationLookupItem:
    booking = (
        db.query(ShopBooking)
        .filter(
            uuid_eq(ShopBooking.entitlement_id, ent.id),
            ShopBooking.status == "booked",
        )
        .order_by(ShopBooking.booked_date.asc())
        .first()
    )
    last_v = (
        db.query(ShopVerification)
        .filter(uuid_eq(ShopVerification.entitlement_id, ent.id), ShopVerification.status == "success")
        .order_by(ShopVerification.created_at.desc())
        .first()
    )
    op_name = None
    if last_v and last_v.operator_id:
        op = db.query(User).filter(uuid_eq(User.id, last_v.operator_id)).first()
        op_name = (op.display_name or op.phone) if op else None
    slot = None
    if booking:
        slot = f"{booking.booked_date} {booking.booked_time_slot}"
    mobile = buyer.mobile if buyer else None
    if not mobile:
        order = db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, ent.order_id)).first()
        mobile = order.buyer_mobile_snapshot if order else None
    return VerificationLookupItem(
        entitlement_id=ent.id,
        buyer_id=buyer.id if buyer else ent.buyer_id,
        buyer_mobile_masked=mask_mobile(mobile) if mobile else None,
        product_id=ent.product_id,
        product_name=product.name if product else None,
        product_type=product.type if product else None,
        shop_id=ent.shop_id,
        status=ent.status,
        remaining_count=ent.remaining_count,
        total_count=ent.total_count,
        verify_code=ent.verify_code,
        booking_id=booking.id if booking else None,
        booking_slot=slot,
        last_verified_at=last_v.created_at if last_v else None,
        last_operator_name=op_name,
    )


def lookup_verifications(
    db: Session, ctx: TenantContext, body: VerificationLookupRequest
) -> VerificationLookupResponse:
    mobile = (body.mobile or "").strip()
    code = (body.verify_code or "").strip()
    if code:
        code = code.upper() if not code.isdigit() else code
    if not mobile and not code:
        raise HTTPException(status_code=422, detail="请输入有效核销码")
    if code and not re.fullmatch(r"\d{6}|[0-9A-Z]{6,16}", code):
        raise HTTPException(status_code=422, detail="请输入有效核销码")

    q = (
        db.query(ShopEntitlement, ShopBuyer, ShopProduct)
        .outerjoin(ShopBuyer, ShopBuyer.id == ShopEntitlement.buyer_id)
        .outerjoin(ShopProduct, ShopProduct.id == ShopEntitlement.product_id)
        .filter(uuid_eq(ShopEntitlement.tenant_id, ctx.tenant_id))
    )
    if code:
        q = q.filter(ShopEntitlement.verify_code == code)
    if mobile:
        if not re.fullmatch(r"1\d{10}", mobile):
            raise HTTPException(status_code=422, detail="手机号格式不正确")
        q = q.filter(ShopBuyer.mobile == mobile)

    rows = q.order_by(ShopEntitlement.created_at.desc()).limit(50).all()
    items = [_lookup_item(db, ent, buyer, product) for ent, buyer, product in rows]

    if not items:
        return VerificationLookupResponse(
            result="invalid",
            message="核销码不存在或已过期，请核对后重试。",
            items=[],
        )

    if len(items) > 1 and not code:
        return VerificationLookupResponse(result="multi", message="找到多条权益，请选择后核销", items=items)

    item = items[0]
    if item.status == "revoked":
        return VerificationLookupResponse(
            result="refunded",
            message="订单已退款，不可再次核销。",
            item=item,
            items=items,
        )
    if item.status == "expired" or (item.remaining_count is not None and item.remaining_count <= 0):
        if item.last_verified_at:
            when = _fmt_md_hm(item.last_verified_at)
            who = item.last_operator_name or "—"
            msg = f"{when} · 操作人：{who}" if when else f"操作人：{who}"
            return VerificationLookupResponse(
                result="already_used",
                message=msg,
                item=item,
                items=items,
            )
        return VerificationLookupResponse(
            result="exhausted",
            message="权益次数已用尽，不可核销。",
            item=item,
            items=items,
        )
    if item.status != "active":
        return VerificationLookupResponse(
            result="invalid",
            message="核销码不存在或已过期，请核对后重试。",
            item=item,
            items=items,
        )
    return VerificationLookupResponse(result="can_redeem", message="校验通过", item=item, items=items)


def execute_verification(
    db: Session, ctx: TenantContext, body: VerificationExecuteRequest
) -> VerificationOut:
    if body.idempotency_key:
        existing = (
            db.query(ShopVerification)
            .filter(ShopVerification.idempotency_key == body.idempotency_key)
            .first()
        )
        if existing:
            if existing.tenant_id != ctx.tenant_id:
                raise HTTPException(status_code=409, detail="幂等键冲突")
            ent = (
                db.query(ShopEntitlement)
                .filter(uuid_eq(ShopEntitlement.id, existing.entitlement_id))
                .first()
            )
            snaps = _remaining_snapshots(db, [existing], {ent.id: ent} if ent else {})
            before, after = snaps.get(existing.id, (None, None))
            return _verification_out(
                db, existing, ent, remaining_before=before, remaining_after=after
            )

    ent = (
        db.query(ShopEntitlement)
        .filter(
            uuid_eq(ShopEntitlement.id, body.entitlement_id),
            uuid_eq(ShopEntitlement.tenant_id, ctx.tenant_id),
        )
        .first()
    )
    if not ent:
        raise HTTPException(status_code=404, detail="权益不存在")
    if ent.status == "revoked":
        raise HTTPException(status_code=409, detail="权益已撤销，不可核销")
    if ent.remaining_count is not None and ent.remaining_count <= 0:
        raise HTTPException(status_code=409, detail="次数已用尽")
    if ent.status == "consumed":
        raise HTTPException(status_code=409, detail="次数已用尽")
    if ent.status != "active":
        raise HTTPException(status_code=409, detail="权益不可核销")
    if ent.remaining_count is not None and body.deducted_count > ent.remaining_count:
        raise HTTPException(status_code=409, detail="扣减次数超过剩余")

    shop = (
        db.query(ShopStore)
        .filter(uuid_eq(ShopStore.id, body.shop_id or ent.shop_id))
        .first()
    )
    if not shop or shop.tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=404, detail="店铺不存在")
    if shop.id != ent.shop_id and not bool(shop.allow_cross_shop_redeem):
        raise HTTPException(status_code=409, detail="未开启跨店核销")

    booking = None
    if body.booking_id:
        booking = (
            db.query(ShopBooking)
            .filter(
                uuid_eq(ShopBooking.id, body.booking_id),
                uuid_eq(ShopBooking.tenant_id, ctx.tenant_id),
                uuid_eq(ShopBooking.entitlement_id, ent.id),
            )
            .first()
        )
        if not booking:
            raise HTTPException(status_code=404, detail="预约不存在")
        if booking.status != "booked":
            raise HTTPException(status_code=409, detail="预约状态不可核销")
    else:
        booking = (
            db.query(ShopBooking)
            .filter(
                uuid_eq(ShopBooking.entitlement_id, ent.id),
                ShopBooking.status == "booked",
                ShopBooking.slot_id.is_(None),
            )
            .order_by(ShopBooking.created_at.desc())
            .first()
        )
        if booking is None:
            buyer_id = _valid_booking_buyer_id(db, ent)
            if buyer_id:
                booking = ShopBooking(
                    id=uuid.uuid4(),
                    tenant_id=ent.tenant_id,
                    shop_id=shop.id,
                    buyer_id=buyer_id,
                    entitlement_id=ent.id,
                    service_product_id=ent.product_id,
                    slot_id=None,
                    status="completed",
                    booked_date=_now().date(),
                    booked_time_slot="次数卡",
                )
                db.add(booking)
                db.flush()

    if ent.remaining_count is not None:
        ent.remaining_count = int(ent.remaining_count) - int(body.deducted_count)
        if ent.remaining_count <= 0:
            ent.remaining_count = 0
            ent.status = "consumed"

    v = ShopVerification(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        shop_id=shop.id,
        buyer_id=ent.buyer_id,
        entitlement_id=ent.id,
        booking_id=booking.id if booking else None,
        type="times_card_deduct",
        status="success",
        operator_id=ctx.user.id,
        verify_code=ent.verify_code,
        idempotency_key=body.idempotency_key,
        deducted_count=body.deducted_count,
    )
    db.add(v)
    if booking:
        booking.status = "completed"
        v.booking_id = booking.id
    db.commit()
    db.refresh(v)
    db.refresh(ent)
    after = ent.remaining_count
    before = (int(after) + int(v.deducted_count or 0)) if after is not None else None
    return _verification_out(db, v, ent, remaining_before=before, remaining_after=after)


def list_verifications(
    db: Session,
    ctx: TenantContext,
    *,
    page: int,
    page_size: int,
    list_own: bool = False,
    q: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    shop_id: UUID | None = None,
    operator_id: UUID | None = None,
) -> tuple[list[VerificationOut], int]:
    query = db.query(ShopVerification).filter(uuid_eq(ShopVerification.tenant_id, ctx.tenant_id))
    if shop_id is not None:
        query = query.filter(uuid_eq(ShopVerification.shop_id, shop_id))
    if list_own:
        query = query.filter(uuid_eq(ShopVerification.operator_id, ctx.user.id))
    if operator_id is not None:
        query = query.filter(uuid_eq(ShopVerification.operator_id, operator_id))
    if q:
        like = f"%{q.strip()}%"
        buyer_ids = [
            b.id
            for b in db.query(ShopBuyer)
            .filter(uuid_eq(ShopBuyer.tenant_id, ctx.tenant_id), ShopBuyer.mobile.ilike(like))
            .all()
        ]
        query = query.filter(
            (ShopVerification.verify_code.ilike(like))
            | (ShopVerification.buyer_id.in_(buyer_ids or [uuid.uuid4()]))
        )
    start = _parse_created_bound(created_from, end=False)
    stop = _parse_created_bound(created_to, end=True)
    if start is not None:
        query = query.filter(ShopVerification.created_at >= start)
    if stop is not None:
        query = query.filter(ShopVerification.created_at < stop)
    total = query.count()
    rows = (
        query.order_by(ShopVerification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    ents = {
        e.id: e
        for e in db.query(ShopEntitlement)
        .filter(ShopEntitlement.id.in_([r.entitlement_id for r in rows] or [uuid.uuid4()]))
        .all()
    }
    snaps = _remaining_snapshots(db, rows, ents)
    packed = []
    for r in rows:
        before, after = snaps.get(r.id, (None, None))
        packed.append(
            _verification_out(
                db, r, ents.get(r.entitlement_id), remaining_before=before, remaining_after=after
            )
        )
    return packed, total


def export_verifications_csv(
    db: Session,
    ctx: TenantContext,
    *,
    list_own: bool = False,
    q: str | None = None,
    shop_id: UUID | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    operator_id: UUID | None = None,
) -> str:
    items, total = list_verifications(
        db,
        ctx,
        page=1,
        page_size=5000,
        list_own=list_own,
        q=q,
        shop_id=shop_id,
        created_from=created_from,
        created_to=created_to,
        operator_id=operator_id,
    )
    if total > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    lines = ["核销时间,核销码,买家,商品,预约时段,操作人,扣次"]
    for i in items:
        lines.append(
            ",".join(
                [
                    str(i.created_at or ""),
                    i.verify_code or "",
                    i.buyer_mobile_masked or "",
                    (i.product_name or "").replace(",", " "),
                    (i.booking_slot or "").replace(",", " "),
                    (i.operator_name or "").replace(",", " "),
                    str(i.deducted_count),
                ]
            )
        )
    return "\n".join(lines)


def create_verification_export_task(
    db: Session, ctx: TenantContext, body: VerificationExportRequest | None = None
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or VerificationExportRequest()
    filters = {
        "q": body.q,
        "shop_id": str(body.shop_id) if body.shop_id else None,
        "created_from": body.created_from,
        "created_to": body.created_to,
        "operator_id": str(body.operator_id) if body.operator_id else None,
    }
    csv_text = export_verifications_csv(
        db,
        ctx,
        list_own=False,
        q=body.q,
        shop_id=body.shop_id,
        created_from=body.created_from,
        created_to=body.created_to,
        operator_id=body.operator_id,
    )
    return export_task_service.persist_csv_task(
        db,
        ctx,
        resource="verifications",
        file_name="verifications.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_verification_export_task(
    db: Session, ctx: TenantContext, task_id: UUID
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task(db, ctx, task_id, "verifications")


def read_verification_export_file(db: Session, ctx: TenantContext, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file(db, ctx, task_id, "verifications")


def list_verification_operators(
    db: Session, ctx: TenantContext, *, shop_id: UUID | None = None
) -> list[dict]:
    q = db.query(ShopVerification.operator_id).filter(
        uuid_eq(ShopVerification.tenant_id, ctx.tenant_id),
        ShopVerification.operator_id.isnot(None),
    )
    if shop_id is not None:
        q = q.filter(uuid_eq(ShopVerification.shop_id, shop_id))
    ids = [r[0] for r in q.distinct().all() if r[0]]
    if not ids:
        return []
    users = db.query(User).filter(User.id.in_(ids)).all()
    return [
        {
            "user_id": str(u.id),
            "display_name": ((u.display_name or "").strip() or u.phone or "—"),
        }
        for u in users
    ]


def get_verification(
    db: Session, ctx: TenantContext, verification_id: UUID, *, list_own: bool = False
) -> VerificationOut:
    v = (
        db.query(ShopVerification)
        .filter(
            uuid_eq(ShopVerification.id, verification_id),
            uuid_eq(ShopVerification.tenant_id, ctx.tenant_id),
        )
        .first()
    )
    if not v:
        raise HTTPException(status_code=404, detail="核销记录不存在")
    if list_own and v.operator_id != ctx.user.id:
        raise HTTPException(status_code=404, detail="核销记录不存在")
    ent = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.id, v.entitlement_id)).first()
    snaps = _remaining_snapshots(db, [v], {ent.id: ent} if ent else {})
    before, after = snaps.get(v.id, (None, None))
    return _verification_out(db, v, ent, remaining_before=before, remaining_after=after)


def create_booking(db: Session, buyer: ShopBuyer, body: BookingCreateRequest) -> BookingOut:
    from app.models.shop import ShopServiceOffer
    from app.services.shop import service_offer_service

    ent = (
        db.query(ShopEntitlement)
        .filter(uuid_eq(ShopEntitlement.id, body.entitlement_id))
        .first()
    )
    if not ent:
        raise HTTPException(status_code=404, detail="权益不存在")
    if ent.buyer_id != buyer.id:
        order = db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, ent.order_id)).first()
        same_mobile = bool(buyer.mobile and order and order.buyer_mobile_snapshot == buyer.mobile)
        claimed = bool(order and order.claimed_buyer_id == buyer.id)
        if not same_mobile and not claimed:
            raise HTTPException(status_code=404, detail="权益不存在")
    if ent.status != "active":
        raise HTTPException(status_code=403, detail="无可用权益，不可预约")
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, ent.product_id)).first()
    if not product or product.type != "service":
        raise HTTPException(status_code=422, detail="仅服务类商品可预约")

    slot_id = body.slot_id
    booked_date = body.booked_date
    slot_label = (body.booked_time_slot or "").strip() if body.booked_time_slot else ""

    # 关联 A07 服务且为预约模式时，须走真实时段
    offer = None
    if product.ref_type == "service_offer" and product.ref_id:
        offer = (
            db.query(ShopServiceOffer)
            .filter(uuid_eq(ShopServiceOffer.id, product.ref_id), ShopServiceOffer.deleted_at.is_(None))
            .first()
        )
        if offer and offer.mode == "booking":
            if not slot_id:
                raise HTTPException(status_code=422, detail="请选择时段")
            if offer.status == "off_sale":
                raise HTTPException(status_code=409, detail="服务已下架，不可新约")

    occupied = None
    times_card = slot_id is None and not booked_date and not slot_label
    if slot_id:
        occupied = service_offer_service.try_occupy_slot(db, slot_id)
        # 本地日历展示字段
        start_at = service_offer_service._aware(occupied.start_at) or occupied.start_at
        end_at = service_offer_service._aware(occupied.end_at) or occupied.end_at
        local_start = start_at.astimezone(service_offer_service.TZ_CN)
        local_end = end_at.astimezone(service_offer_service.TZ_CN)
        booked_date = local_start.date()
        slot_label = f"{local_start.strftime('%H:%M')}-{local_end.strftime('%H:%M')}"
        conflict = (
            db.query(ShopBooking)
            .filter(
                uuid_eq(ShopBooking.entitlement_id, ent.id),
                uuid_eq(ShopBooking.slot_id, slot_id),
                ShopBooking.status == "booked",
            )
            .first()
        )
        if conflict:
            service_offer_service.release_slot(db, slot_id)
            raise HTTPException(status_code=409, detail="重复预约")
    elif times_card:
        existing = (
            db.query(ShopBooking)
            .filter(
                uuid_eq(ShopBooking.entitlement_id, ent.id),
                ShopBooking.status == "booked",
                ShopBooking.slot_id.is_(None),
            )
            .order_by(ShopBooking.created_at.desc())
            .first()
        )
        if existing:
            return _pack_bookings(db, [existing])[0]
        booked_date = _now().date()
        slot_label = "次数卡"
    else:
        if not booked_date or not slot_label:
            raise HTTPException(status_code=422, detail="请选择时段")
        conflict = (
            db.query(ShopBooking)
            .filter(
                uuid_eq(ShopBooking.entitlement_id, ent.id),
                ShopBooking.booked_date == booked_date,
                ShopBooking.booked_time_slot == slot_label,
                ShopBooking.status == "booked",
            )
            .first()
        )
        if conflict:
            raise HTTPException(status_code=409, detail="该时段已被占用")

    b = ShopBooking(
        id=uuid.uuid4(),
        tenant_id=buyer.tenant_id,
        shop_id=ent.shop_id,
        buyer_id=buyer.id,
        entitlement_id=ent.id,
        service_product_id=ent.product_id,
        slot_id=slot_id,
        status="booked",
        booked_date=booked_date,
        booked_time_slot=slot_label,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return _pack_bookings(db, [b])[0]


def mark_booking_cancelled(
    db: Session, b: ShopBooking, reason: str, *, now: datetime | None = None
) -> None:
    """待服务 → 已取消并释放容量。不发站内信。"""
    from app.services.shop import service_offer_service

    if b.status != "booked":
        return
    b.status = "cancelled"
    b.cancelled_at = now or _now()
    b.cancel_reason = reason
    service_offer_service.release_slot(db, b.slot_id)


def cancel_booking(
    db: Session, buyer: ShopBuyer, booking_id: UUID, body: BookingCancelRequest
) -> BookingOut:
    from app.services.shop import service_offer_service

    b = db.query(ShopBooking).filter(uuid_eq(ShopBooking.id, booking_id)).first()
    if not b:
        raise HTTPException(status_code=404, detail="预约不存在")
    ent_ids = _buyer_entitlement_ids(db, buyer)
    if b.buyer_id != buyer.id and b.entitlement_id not in ent_ids:
        raise HTTPException(status_code=404, detail="预约不存在")
    if b.status != "booked":
        raise HTTPException(status_code=409, detail="当前状态不可取消")
    # 预约模式：须提前 2 小时
    if b.slot_id:
        from app.models.shop import ShopServiceSlot

        slot = db.query(ShopServiceSlot).filter(uuid_eq(ShopServiceSlot.id, b.slot_id)).first()
        if slot:
            start_at = service_offer_service._aware(slot.start_at) or slot.start_at
            if _now() >= start_at - timedelta(hours=2):
                raise HTTPException(status_code=409, detail="距开始不足 2 小时，不可取消")
    mark_booking_cancelled(db, b, body.reason or "buyer_cancel")
    db.commit()
    db.refresh(b)
    return _pack_bookings(db, [b])[0]


def _buyer_row_exists(db: Session, buyer_id: UUID | None) -> bool:
    if not buyer_id:
        return False
    return db.query(ShopBuyer.id).filter(uuid_eq(ShopBuyer.id, buyer_id)).first() is not None


def _valid_booking_buyer_id(
    db: Session, ent: ShopEntitlement, *, fallback: UUID | None = None
) -> UUID | None:
    if _buyer_row_exists(db, ent.buyer_id):
        return ent.buyer_id
    order = (
        db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, ent.order_id)).first()
        if ent.order_id
        else None
    )
    if order and _buyer_row_exists(db, order.claimed_buyer_id):
        return order.claimed_buyer_id
    if _buyer_row_exists(db, fallback):
        return fallback
    if order and order.buyer_mobile_snapshot:
        found = (
            db.query(ShopBuyer)
            .filter(
                uuid_eq(ShopBuyer.tenant_id, ent.tenant_id),
                ShopBuyer.mobile == order.buyer_mobile_snapshot,
            )
            .first()
        )
        if found:
            return found.id
    return None


def _buyer_entitlement_ids(db: Session, buyer: ShopBuyer) -> list[UUID]:
    if buyer.mobile:
        rows = (
            db.query(ShopEntitlement.id)
            .outerjoin(ShopOrder, ShopOrder.id == ShopEntitlement.order_id)
            .filter(uuid_eq(ShopEntitlement.tenant_id, buyer.tenant_id))
            .filter(
                or_(
                    uuid_eq(ShopEntitlement.buyer_id, buyer.id),
                    ShopOrder.buyer_mobile_snapshot == buyer.mobile,
                    uuid_eq(ShopOrder.claimed_buyer_id, buyer.id),
                )
            )
            .all()
        )
        return [r[0] for r in rows]
    return [
        r[0]
        for r in db.query(ShopEntitlement.id)
        .filter(uuid_eq(ShopEntitlement.buyer_id, buyer.id))
        .all()
    ]


def _backfill_completed_bookings_from_verifications(db: Session, buyer: ShopBuyer) -> None:
    """次数卡核销未写预约时，补一条已完成记录，便于 M10c「已完成/取消」可见。"""
    ent_ids = _buyer_entitlement_ids(db, buyer)
    if not ent_ids:
        return
    orphans = (
        db.query(ShopVerification)
        .filter(
            uuid_eq(ShopVerification.tenant_id, buyer.tenant_id),
            ShopVerification.status == "success",
            ShopVerification.booking_id.is_(None),
            ShopVerification.entitlement_id.in_(ent_ids),
        )
        .all()
    )
    if not orphans:
        return
    changed = False
    for v in orphans:
        ent = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.id, v.entitlement_id)).first()
        if not ent:
            continue
        buyer_id = _valid_booking_buyer_id(db, ent, fallback=buyer.id)
        if not buyer_id:
            continue
        when = v.created_at or _now()
        booked_date = when.date() if hasattr(when, "date") else _now().date()
        b = ShopBooking(
            id=uuid.uuid4(),
            tenant_id=ent.tenant_id,
            shop_id=v.shop_id or ent.shop_id,
            buyer_id=buyer_id,
            entitlement_id=ent.id,
            service_product_id=ent.product_id,
            slot_id=None,
            status="completed",
            booked_date=booked_date,
            booked_time_slot="次数卡",
        )
        db.add(b)
        db.flush()
        v.booking_id = b.id
        changed = True
    if changed:
        db.commit()


def list_bookings_buyer(
    db: Session, buyer: ShopBuyer, *, page: int, page_size: int
) -> tuple[list[BookingOut], int]:
    _backfill_completed_bookings_from_verifications(db, buyer)
    ent_ids = _buyer_entitlement_ids(db, buyer)
    conds = [uuid_eq(ShopBooking.buyer_id, buyer.id)]
    if ent_ids:
        conds.append(ShopBooking.entitlement_id.in_(ent_ids))
    q = db.query(ShopBooking).filter(
        uuid_eq(ShopBooking.tenant_id, buyer.tenant_id),
        or_(*conds),
    )
    total = q.count()
    rows = (
        q.order_by(ShopBooking.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _pack_bookings(db, rows), total


def _filter_merchant_bookings(
    db: Session,
    ctx: TenantContext,
    query,
    *,
    booked_date: date | None = None,
    booked_from: date | None = None,
    booked_to: date | None = None,
    buyer_id: UUID | None = None,
    shop_id: UUID | None = None,
    status: str | None = None,
    q: str | None = None,
):
    if shop_id is not None:
        query = query.filter(uuid_eq(ShopBooking.shop_id, shop_id))
    if booked_date is not None:
        query = query.filter(ShopBooking.booked_date == booked_date)
    if booked_from is not None:
        query = query.filter(ShopBooking.booked_date >= booked_from)
    if booked_to is not None:
        query = query.filter(ShopBooking.booked_date <= booked_to)
    if buyer_id is not None:
        query = query.filter(uuid_eq(ShopBooking.buyer_id, buyer_id))
    if status:
        query = query.filter(ShopBooking.status == status)
    raw = (q or "").strip()
    if raw:
        like = f"%{raw}%"
        prod_ids = [
            pid
            for (pid,) in db.query(ShopProduct.id).filter(
                uuid_eq(ShopProduct.tenant_id, ctx.tenant_id),
                ShopProduct.name.ilike(like),
            ).all()
        ]
        ent_ids = [
            eid
            for (eid,) in db.query(ShopEntitlement.id).filter(
                uuid_eq(ShopEntitlement.tenant_id, ctx.tenant_id),
                ShopEntitlement.verify_code.ilike(like),
            ).all()
        ]
        order_ids = [
            oid
            for (oid,) in db.query(ShopOrder.id).filter(
                uuid_eq(ShopOrder.tenant_id, ctx.tenant_id),
                ShopOrder.order_no.ilike(like),
            ).all()
        ]
        ent_by_order = [
            eid
            for (eid,) in db.query(ShopEntitlement.id).filter(
                ShopEntitlement.order_id.in_(order_ids or [uuid.uuid4()])
            ).all()
        ]
        hex_q = raw.upper().replace("BK", "").replace("-", "")
        linked = list(ent_ids) + list(ent_by_order)
        clauses = [
            ShopBooking.service_product_id.in_(prod_ids or [uuid.uuid4()]),
            ShopBooking.entitlement_id.in_(linked or [uuid.uuid4()]),
        ]
        if len(hex_q) >= 4:
            clauses.append(cast(ShopBooking.id, SAString).ilike(f"%{hex_q[-6:]}%"))
        query = query.filter(or_(*clauses))
    return query


def list_bookings_merchant(
    db: Session,
    ctx: TenantContext,
    *,
    page: int,
    page_size: int,
    booked_date: date | None = None,
    booked_from: date | None = None,
    booked_to: date | None = None,
    buyer_id: UUID | None = None,
    shop_id: UUID | None = None,
    status: str | None = None,
    q: str | None = None,
) -> tuple[list[BookingOut], int, dict[str, int]]:
    base = db.query(ShopBooking).filter(uuid_eq(ShopBooking.tenant_id, ctx.tenant_id))
    if shop_id is not None:
        base = base.filter(uuid_eq(ShopBooking.shop_id, shop_id))
    if buyer_id is not None:
        base = base.filter(uuid_eq(ShopBooking.buyer_id, buyer_id))
    counts = {
        "all": base.count(),
        "booked": base.filter(ShopBooking.status == "booked").count(),
        "completed": base.filter(ShopBooking.status == "completed").count(),
        "cancelled": base.filter(ShopBooking.status == "cancelled").count(),
    }
    query = _filter_merchant_bookings(
        db,
        ctx,
        base,
        booked_date=booked_date,
        booked_from=booked_from,
        booked_to=booked_to,
        buyer_id=None,
        shop_id=None,
        status=status,
        q=q,
    )
    total = query.count()
    rows = (
        query.order_by(ShopBooking.booked_date.desc(), ShopBooking.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _pack_bookings(db, rows), total, counts


_BOOKING_SOURCE_ZH = {
    "expired_unredeemed": "过期未核销",
    "slot_closed": "关闭时段",
    "buyer_cancel": "买家取消",
    "entitlement_revoked": "权益撤销",
}


def export_bookings_csv(
    db: Session,
    ctx: TenantContext,
    *,
    booked_date: date | None = None,
    booked_from: date | None = None,
    booked_to: date | None = None,
    buyer_id: UUID | None = None,
    shop_id: UUID | None = None,
    status: str | None = None,
    q: str | None = None,
    columns: list[str] | None = None,
    raise_too_many: bool = False,
) -> str:
    import csv
    import io

    items, total, _counts = list_bookings_merchant(
        db,
        ctx,
        page=1,
        page_size=5000,
        booked_date=booked_date,
        booked_from=booked_from,
        booked_to=booked_to,
        buyer_id=buyer_id,
        shop_id=shop_id,
        status=status,
        q=q,
    )
    if raise_too_many and total > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    default_headers = ["预约号", "服务", "店铺", "时段", "状态", "核销码", "来源订单", "创建时间"]
    col_map = {
        "booking_no": ["预约号"],
        "product_name": ["服务"],
        "shop_name": ["店铺"],
        "slot": ["时段"],
        "status": ["状态"],
        "verify_code": ["核销码"],
        "order_no": ["来源订单"],
        "created_at": ["创建时间"],
        "cancel_source": ["来源"],
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
    for it in items:
        slot = f"{it.booked_date} {it.booked_time_slot}".strip()
        created = it.created_at.isoformat(sep=" ", timespec="minutes") if it.created_at else ""
        source = ""
        if it.status == "cancelled":
            source = _BOOKING_SOURCE_ZH.get(it.cancel_reason or "", "")
        values = {
            "预约号": it.booking_no or "",
            "服务": it.product_name or "",
            "店铺": it.shop_name or "",
            "时段": slot,
            "状态": it.status_label or it.status or "",
            "核销码": it.verify_code or "",
            "来源订单": it.order_no or "",
            "创建时间": created,
            "来源": source,
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_booking_export_task(
    db: Session, ctx: TenantContext, body: BookingExportRequest | None = None
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or BookingExportRequest()
    filters = {
        "booked_date": str(body.booked_date) if body.booked_date else None,
        "booked_from": str(body.booked_from) if body.booked_from else None,
        "booked_to": str(body.booked_to) if body.booked_to else None,
        "buyer_id": str(body.buyer_id) if body.buyer_id else None,
        "shop_id": str(body.shop_id) if body.shop_id else None,
        "status": body.status,
        "q": body.q,
        "columns": body.columns,
    }
    csv_text = export_bookings_csv(
        db,
        ctx,
        booked_date=body.booked_date,
        booked_from=body.booked_from,
        booked_to=body.booked_to,
        buyer_id=body.buyer_id,
        shop_id=body.shop_id,
        status=body.status,
        q=body.q,
        columns=body.columns,
        raise_too_many=True,
    )
    return export_task_service.persist_csv_task(
        db,
        ctx,
        resource="bookings",
        file_name="shop-bookings.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_booking_export_task(db: Session, ctx: TenantContext, task_id: UUID) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task(db, ctx, task_id, "bookings")


def read_booking_export_file(db: Session, ctx: TenantContext, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file(db, ctx, task_id, "bookings")


def get_booking_merchant(db: Session, ctx: TenantContext, booking_id: UUID) -> BookingOut:
    b = (
        db.query(ShopBooking)
        .filter(
            uuid_eq(ShopBooking.id, booking_id),
            uuid_eq(ShopBooking.tenant_id, ctx.tenant_id),
        )
        .first()
    )
    if not b:
        raise HTTPException(status_code=404, detail="预约不存在")
    return _pack_bookings(db, [b])[0]


def create_invoice(db: Session, buyer: ShopBuyer, body: InvoiceCreateRequest) -> InvoiceOut:
    from app.services.shop.order_service import get_order_for_buyer

    order = get_order_for_buyer(db, buyer, body.order_id, commit_heal=False)
    if order.status == "refunded":
        raise HTTPException(status_code=409, detail="已退款订单不可申请发票")
    if order.status != "paid":
        raise HTTPException(status_code=409, detail="仅已付款订单可申请发票")

    title_type = (body.title_type or "").strip()
    if title_type not in ("person", "company"):
        raise HTTPException(status_code=422, detail="抬头类型无效")
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="请填写发票抬头")
    tax_no = (body.tax_no or "").strip() or None
    if title_type == "company":
        if not tax_no or not re.fullmatch(r"[0-9A-Z]{15,20}", tax_no.upper()):
            raise HTTPException(status_code=422, detail="企业抬头须填写合法税号")
        tax_no = tax_no.upper()
    else:
        tax_no = None
    email = (body.email or "").strip()
    if not email:
        raise HTTPException(status_code=422, detail="请填写邮箱")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="邮箱格式错误")

    blocking = (
        db.query(ShopInvoiceRequest)
        .filter(
            uuid_eq(ShopInvoiceRequest.order_id, order.id),
            ShopInvoiceRequest.status.in_(("pending", "submitted", "issued")),
        )
        .first()
    )
    if blocking:
        raise HTTPException(status_code=409, detail="该订单已有进行中或已开具的发票申请")

    rejected = (
        db.query(ShopInvoiceRequest)
        .filter(
            uuid_eq(ShopInvoiceRequest.order_id, order.id),
            ShopInvoiceRequest.status == "rejected",
        )
        .order_by(ShopInvoiceRequest.created_at.desc())
        .first()
    )
    invoice_type = body.invoice_type if body.invoice_type in ("normal", "special") else "normal"
    amount = order.paid_amount_cents or order.amount_cents
    if rejected:
        # F5：rejected → submitted，更新同一条，清空驳回字段，刷新申请时间
        rejected.invoice_type = invoice_type
        rejected.title_type = title_type
        rejected.title = title
        rejected.tax_no = tax_no
        rejected.bank_name = body.bank_name
        rejected.bank_account = body.bank_account
        rejected.address = body.address
        rejected.phone = body.phone
        rejected.email = email
        rejected.amount_cents = amount
        rejected.status = "submitted"
        rejected.reject_reason = None
        rejected.operator_id = None
        rejected.invoice_no = None
        rejected.invoice_url = None
        rejected.remark = None
        rejected.issued_at = None
        rejected.created_at = _now()
        order.invoice_status = "submitted"
        db.commit()
        db.refresh(rejected)
        return _invoice_out(rejected, order)

    inv = ShopInvoiceRequest(
        id=uuid.uuid4(),
        tenant_id=order.tenant_id,
        shop_id=order.shop_id,
        buyer_id=buyer.id,
        order_id=order.id,
        invoice_type=invoice_type,
        title_type=title_type,
        title=title,
        tax_no=tax_no,
        bank_name=body.bank_name,
        bank_account=body.bank_account,
        address=body.address,
        phone=body.phone,
        email=email,
        amount_cents=amount,
        status="submitted",
    )
    db.add(inv)
    order.invoice_status = "submitted"
    db.commit()
    db.refresh(inv)
    return _invoice_out(inv, order)


def _pack_invoice_rows(db: Session, rows: list) -> list[InvoiceOut]:
    orders = {
        o.id: o
        for o in db.query(ShopOrder)
        .filter(ShopOrder.id.in_([r.order_id for r in rows] or [uuid.uuid4()]))
        .all()
    }
    op_ids = {r.operator_id for r in rows if getattr(r, "operator_id", None)}
    ops: dict = {}
    if op_ids:
        ops = {u.id: u for u in db.query(User).filter(User.id.in_(list(op_ids))).all()}
    packed: list[InvoiceOut] = []
    for r in rows:
        u = ops.get(r.operator_id) if r.operator_id else None
        name = None
        if u:
            name = ((u.display_name or "").strip() or u.phone or "").strip() or None
        packed.append(_invoice_out(r, orders.get(r.order_id), operator_name=name))
    return packed


def list_invoices_buyer(
    db: Session, buyer: ShopBuyer, *, page: int, page_size: int
) -> tuple[list[InvoiceOut], int]:
    from app.services.shop.order_service import buyer_order_clause

    q = (
        db.query(ShopInvoiceRequest)
        .join(ShopOrder, ShopOrder.id == ShopInvoiceRequest.order_id)
        .filter(
            uuid_eq(ShopInvoiceRequest.tenant_id, buyer.tenant_id),
            or_(
                uuid_eq(ShopInvoiceRequest.buyer_id, buyer.id),
                buyer_order_clause(buyer),
            ),
        )
    )
    total = q.count()
    rows = (
        q.order_by(ShopInvoiceRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _pack_invoice_rows(db, rows), total


def list_invoices_merchant(
    db: Session,
    ctx: TenantContext,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    q: str | None = None,
    buyer_id: UUID | None = None,
    shop_id: UUID | None = None,
    title_type: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
) -> tuple[list[InvoiceOut], int, dict[str, int]]:
    base = db.query(ShopInvoiceRequest).filter(uuid_eq(ShopInvoiceRequest.tenant_id, ctx.tenant_id))
    if shop_id is not None:
        base = base.filter(uuid_eq(ShopInvoiceRequest.shop_id, shop_id))
    if buyer_id is not None:
        base = base.filter(uuid_eq(ShopInvoiceRequest.buyer_id, buyer_id))
    counts = {"all": base.count(), "submitted": 0, "issued": 0, "rejected": 0}
    for st in ("submitted", "pending", "issued", "rejected"):
        c = base.filter(ShopInvoiceRequest.status == st).count()
        if st == "pending":
            counts["submitted"] += c
        else:
            counts[st] = counts.get(st, 0) + c

    query = base
    if status in ("submitted", "pending"):
        query = query.filter(ShopInvoiceRequest.status.in_(("submitted", "pending")))
    elif status:
        query = query.filter(ShopInvoiceRequest.status == status)
    if title_type in ("person", "company"):
        query = query.filter(ShopInvoiceRequest.title_type == title_type)
    if created_from is not None:
        query = query.filter(ShopInvoiceRequest.created_at >= _date_start(created_from))
    if created_to is not None:
        query = query.filter(ShopInvoiceRequest.created_at < _date_end_excl(created_to))
    if q:
        like = f"%{q.strip()}%"
        order_ids = [
            o.id
            for o in db.query(ShopOrder)
            .filter(uuid_eq(ShopOrder.tenant_id, ctx.tenant_id), ShopOrder.order_no.ilike(like))
            .all()
        ]
        query = query.filter(
            (ShopInvoiceRequest.title.ilike(like))
            | (ShopInvoiceRequest.order_id.in_(order_ids or [uuid.uuid4()]))
        )
    total = query.count()
    rows = (
        query.order_by(ShopInvoiceRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _pack_invoice_rows(db, rows), total, counts


def get_invoice_merchant(db: Session, ctx: TenantContext, invoice_id: UUID) -> InvoiceOut:
    inv = (
        db.query(ShopInvoiceRequest)
        .filter(
            uuid_eq(ShopInvoiceRequest.id, invoice_id),
            uuid_eq(ShopInvoiceRequest.tenant_id, ctx.tenant_id),
        )
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="开票申请不存在")
    order = db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, inv.order_id)).first()
    return _invoice_out(inv, order, operator_name=_operator_name(db, inv.operator_id))


_INVOICE_STATUS_ZH = {
    "submitted": "待处理",
    "pending": "待处理",
    "issued": "已开票",
    "rejected": "已驳回",
}


def export_invoices_csv(
    db: Session,
    ctx: TenantContext,
    *,
    status: str | None = None,
    q: str | None = None,
    shop_id: UUID | None = None,
    title_type: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
) -> str:
    items, total, _ = list_invoices_merchant(
        db,
        ctx,
        page=1,
        page_size=5000,
        status=status,
        q=q,
        shop_id=shop_id,
        title_type=title_type,
        created_from=created_from,
        created_to=created_to,
    )
    if total > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    lines = ["订单,抬头,类型,税号,邮箱,金额,申请时间,状态,发票号码,处理人,开具时间"]
    for i in items:
        lines.append(
            ",".join(
                [
                    i.order_no or "",
                    (i.title or "").replace(",", " "),
                    "企业" if i.title_type == "company" else "个人",
                    i.tax_no or "",
                    i.email or "",
                    f"{(i.amount_cents or 0) / 100:.2f}",
                    str(i.created_at or ""),
                    _INVOICE_STATUS_ZH.get(i.status, i.status),
                    i.invoice_no or "",
                    i.operator_name or "",
                    str(i.issued_at or ""),
                ]
            )
        )
    return "\n".join(lines)


def create_invoice_export_task(
    db: Session, ctx: TenantContext, body: InvoiceExportRequest | None = None
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or InvoiceExportRequest()
    filters = {
        "status": body.status,
        "q": body.q,
        "shop_id": str(body.shop_id) if body.shop_id else None,
        "title_type": body.title_type,
        "created_from": str(body.created_from) if body.created_from else None,
        "created_to": str(body.created_to) if body.created_to else None,
    }
    csv = export_invoices_csv(
        db,
        ctx,
        status=body.status,
        q=body.q,
        shop_id=body.shop_id,
        title_type=body.title_type,
        created_from=body.created_from,
        created_to=body.created_to,
    )
    return export_task_service.persist_csv_task(
        db,
        ctx,
        resource="invoices",
        file_name="invoices.csv",
        csv_text=csv,
        filters=filters,
    )


def get_invoice_export_task(
    db: Session, ctx: TenantContext, task_id: UUID
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task(db, ctx, task_id, "invoices")


def read_invoice_export_file(db: Session, ctx: TenantContext, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file(db, ctx, task_id, "invoices")


def _is_openable(status: str) -> bool:
    return status in ("pending", "submitted")


def issue_invoice(
    db: Session, ctx: TenantContext, invoice_id: UUID, body: InvoiceIssueRequest
) -> InvoiceOut:
    inv = (
        db.query(ShopInvoiceRequest)
        .filter(
            uuid_eq(ShopInvoiceRequest.id, invoice_id),
            uuid_eq(ShopInvoiceRequest.tenant_id, ctx.tenant_id),
        )
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="发票申请不存在")
    if not _is_openable(inv.status):
        raise HTTPException(status_code=409, detail="仅待处理申请可开具")
    no = (body.invoice_no or "").strip()
    if not no:
        raise HTTPException(status_code=422, detail="请填写发票号码")
    inv.status = "issued"
    inv.issued_at = _now()
    inv.invoice_no = no
    inv.invoice_url = (body.invoice_url or "").strip() or None
    inv.remark = (body.remark or "").strip() or None
    inv.operator_id = ctx.user.id
    order = db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, inv.order_id)).first()
    if order:
        order.invoice_status = "issued"
    db.commit()
    db.refresh(inv)
    return _invoice_out(inv, order, operator_name=_operator_name(db, inv.operator_id))


def reject_invoice(
    db: Session, ctx: TenantContext, invoice_id: UUID, body: InvoiceRejectRequest
) -> InvoiceOut:
    inv = (
        db.query(ShopInvoiceRequest)
        .filter(
            uuid_eq(ShopInvoiceRequest.id, invoice_id),
            uuid_eq(ShopInvoiceRequest.tenant_id, ctx.tenant_id),
        )
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="发票申请不存在")
    if not _is_openable(inv.status):
        raise HTTPException(status_code=409, detail="仅待处理申请可驳回")
    reason = (body.reason or "").strip()
    if len(reason) < 4:
        raise HTTPException(status_code=422, detail="请填写驳回原因")
    inv.status = "rejected"
    inv.reject_reason = reason
    inv.operator_id = ctx.user.id
    order = db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, inv.order_id)).first()
    if order and order.invoice_status == "submitted":
        order.invoice_status = "none"
    db.commit()
    db.refresh(inv)
    return _invoice_out(inv, order, operator_name=_operator_name(db, inv.operator_id))


def upsert_lesson_progress(
    db: Session,
    buyer: ShopBuyer,
    entitlement_id: UUID,
    lesson_id: UUID,
    body: LessonProgressUpsertRequest,
) -> LessonProgressOut:
    ent = (
        db.query(ShopEntitlement)
        .filter(
            uuid_eq(ShopEntitlement.id, entitlement_id),
            uuid_eq(ShopEntitlement.buyer_id, buyer.id),
        )
        .first()
    )
    if not ent:
        raise HTTPException(status_code=404, detail="权益不存在")
    if ent.status != "active":
        raise HTTPException(status_code=403, detail="权益不可用")

    row = (
        db.query(ShopLessonProgress)
        .filter(
            uuid_eq(ShopLessonProgress.entitlement_id, entitlement_id),
            uuid_eq(ShopLessonProgress.lesson_id, lesson_id),
        )
        .first()
    )
    now = _now()
    if row is None:
        row = ShopLessonProgress(
            id=uuid.uuid4(),
            tenant_id=buyer.tenant_id,
            buyer_id=buyer.id,
            entitlement_id=entitlement_id,
            course_id=body.course_id,
            lesson_id=lesson_id,
            position_sec=body.position_sec,
            progress_pct=body.progress_pct,
            last_learned_at=now,
        )
        db.add(row)
    else:
        row.course_id = body.course_id
        row.position_sec = body.position_sec
        row.progress_pct = body.progress_pct
        row.last_learned_at = now
    db.commit()
    db.refresh(row)
    return _lesson_out(row)


def get_lesson_progress(
    db: Session, buyer: ShopBuyer, entitlement_id: UUID, lesson_id: UUID
) -> LessonProgressOut:
    ent = (
        db.query(ShopEntitlement)
        .filter(
            uuid_eq(ShopEntitlement.id, entitlement_id),
            uuid_eq(ShopEntitlement.buyer_id, buyer.id),
        )
        .first()
    )
    if not ent:
        raise HTTPException(status_code=404, detail="权益不存在")
    row = (
        db.query(ShopLessonProgress)
        .filter(
            uuid_eq(ShopLessonProgress.entitlement_id, entitlement_id),
            uuid_eq(ShopLessonProgress.lesson_id, lesson_id),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="暂无进度")
    return _lesson_out(row)


def set_store_cross_redeem(
    db: Session, ctx: TenantContext, allow: bool, shop_id: UUID | None = None
) -> dict:
    if shop_id:
        shop = (
            db.query(ShopStore)
            .filter(uuid_eq(ShopStore.id, shop_id), uuid_eq(ShopStore.tenant_id, ctx.tenant_id))
            .first()
        )
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
    else:
        shop = _default_shop(db, ctx.tenant_id)
    shop.allow_cross_shop_redeem = bool(allow)
    db.commit()
    return {"shop_id": str(shop.id), "allow_cross_shop_redeem": bool(shop.allow_cross_shop_redeem)}
