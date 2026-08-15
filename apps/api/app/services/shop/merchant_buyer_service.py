"""商家端 A11 买家列表/详情。对照 PRD 01-管理端UI.html #a11 / #a11a。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.shop import (
    ShopBuyer,
    ShopEntitlement,
    ShopLesson,
    ShopLessonProgress,
    ShopOrder,
    ShopProduct,
    ShopStore,
)
from app.schemas.shop_platform import (
    BuyerExportRequest,
    BuyerLearningListResponse,
    BuyerLearningProgressOut,
    MerchantBuyerDetailOut,
    MerchantBuyerOut,
    ShopExportTaskOut,
)
from app.services.shop.buyer_service import mask_mobile


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _register_channel(buyer: ShopBuyer) -> str:
    return "微信" if buyer.wx_openid else "其他"


def _buyer_row(
    db: Session,
    buyer: ShopBuyer,
    *,
    reveal: bool = False,
) -> MerchantBuyerOut:
    paid_statuses = ("paid", "claim_pending", "refunding", "refunded")
    orders = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.buyer_id, buyer.id))
        .order_by(ShopOrder.created_at.desc())
        .all()
    )
    paid = [o for o in orders if o.status in paid_statuses]
    ent_count = (
        db.query(ShopEntitlement)
        .filter(uuid_eq(ShopEntitlement.buyer_id, buyer.id))
        .count()
    )
    source_shop = None
    last_paid = next((o for o in orders if o.status in paid_statuses), None)
    if last_paid:
        shop = db.query(ShopStore).filter(uuid_eq(ShopStore.id, last_paid.shop_id)).first()
        source_shop = shop.name if shop else None
    return MerchantBuyerOut(
        id=buyer.id,
        tenant_id=buyer.tenant_id,
        nickname=buyer.nickname,
        mobile=buyer.mobile if reveal else None,
        mobile_masked=mask_mobile(buyer.mobile),
        account_status="active",
        source_shop_name=source_shop,
        order_count=len(orders),
        entitlement_count=ent_count,
        paid_amount_cents=sum(int(o.paid_amount_cents or o.amount_cents or 0) for o in paid),
        register_channel=_register_channel(buyer),
        last_order_at=orders[0].created_at if orders else None,
        first_order_at=orders[-1].created_at if orders else None,
        created_at=buyer.created_at,
    )


def list_buyers(
    db: Session,
    ctx: TenantContext,
    *,
    page: int,
    page_size: int,
    q: str | None = None,
    tab: str | None = None,
    shop_id: UUID | None = None,
    account_status: str | None = None,
    order_count_min: int | None = None,
    entitlement_count_min: int | None = None,
    registered_from: date | None = None,
    registered_to: date | None = None,
    last_order_from: date | None = None,
    last_order_to: date | None = None,
    buyer_ids: list[UUID] | None = None,
) -> tuple[list[MerchantBuyerOut], int, dict[str, int]]:
    query = db.query(ShopBuyer).filter(uuid_eq(ShopBuyer.tenant_id, ctx.tenant_id))
    if buyer_ids is not None:
        if not buyer_ids:
            return [], 0, {"all": 0, "with_entitlement": 0, "new_7d": 0, "blocked": 0}
        query = query.filter(ShopBuyer.id.in_(buyer_ids))
    if shop_id:
        order_buyer_ids = {
            r[0]
            for r in db.query(ShopOrder.buyer_id)
            .filter(
                uuid_eq(ShopOrder.tenant_id, ctx.tenant_id),
                uuid_eq(ShopOrder.shop_id, shop_id),
                ShopOrder.buyer_id.isnot(None),
            )
            .distinct()
            .all()
        }
        ent_buyer_ids = {
            r[0]
            for r in db.query(ShopEntitlement.buyer_id)
            .filter(
                uuid_eq(ShopEntitlement.tenant_id, ctx.tenant_id),
                uuid_eq(ShopEntitlement.shop_id, shop_id),
                ShopEntitlement.buyer_id.isnot(None),
            )
            .distinct()
            .all()
        }
        scoped = {i for i in order_buyer_ids | ent_buyer_ids if i is not None}
        if not scoped:
            return [], 0, {"all": 0, "with_entitlement": 0, "new_7d": 0, "blocked": 0}
        query = query.filter(ShopBuyer.id.in_(list(scoped)))
    if q:
        qq = q.strip()
        query = query.filter(
            or_(ShopBuyer.mobile.contains(qq), ShopBuyer.nickname.contains(qq))
        )
    all_ids = [b.id for b in query.all()]
    empty_counts = {"all": 0, "with_entitlement": 0, "new_7d": 0, "blocked": 0}
    if not all_ids:
        return [], 0, empty_counts
    buyers_all = (
        db.query(ShopBuyer)
        .filter(ShopBuyer.id.in_(all_ids))
        .order_by(ShopBuyer.created_at.desc())
        .all()
    )
    ent_map = dict(
        db.query(ShopEntitlement.buyer_id, func.count(ShopEntitlement.id))
        .filter(ShopEntitlement.buyer_id.in_(all_ids))
        .group_by(ShopEntitlement.buyer_id)
        .all()
    )
    order_map = {
        row[0]: {"cnt": int(row[1] or 0), "last_at": row[2], "first_at": row[3]}
        for row in db.query(
            ShopOrder.buyer_id,
            func.count(ShopOrder.id),
            func.max(ShopOrder.created_at),
            func.min(ShopOrder.created_at),
        )
        .filter(ShopOrder.buyer_id.in_(all_ids))
        .group_by(ShopOrder.buyer_id)
        .all()
    }
    since = _now() - timedelta(days=7)
    with_ent = {bid for bid, n in ent_map.items() if n}
    recent_new = set()
    for b in buyers_all:
        created = _as_aware(b.created_at)
        if created and created >= since:
            recent_new.add(b.id)
    counts = {
        "all": len(buyers_all),
        "with_entitlement": len(with_ent),
        "new_7d": len(recent_new),
        "blocked": 0,
    }
    filtered = buyers_all
    if tab == "with_entitlement":
        filtered = [b for b in buyers_all if b.id in with_ent]
    elif tab == "new_7d":
        filtered = [b for b in buyers_all if b.id in recent_new]
    elif tab == "blocked":
        filtered = []
    if (account_status or "").strip().lower() == "blocked":
        filtered = []
    elif (account_status or "").strip().lower() == "active":
        pass
    if order_count_min is not None:
        filtered = [
            b for b in filtered if (order_map.get(b.id) or {}).get("cnt", 0) >= order_count_min
        ]
    if entitlement_count_min is not None:
        filtered = [b for b in filtered if int(ent_map.get(b.id) or 0) >= entitlement_count_min]
    if registered_from is not None:
        filtered = [
            b
            for b in filtered
            if _as_aware(b.created_at) and _as_aware(b.created_at).date() >= registered_from
        ]
    if registered_to is not None:
        filtered = [
            b
            for b in filtered
            if _as_aware(b.created_at) and _as_aware(b.created_at).date() <= registered_to
        ]
    if last_order_from is not None:
        filtered = [
            b
            for b in filtered
            if _as_aware((order_map.get(b.id) or {}).get("last_at"))
            and _as_aware((order_map.get(b.id) or {}).get("last_at")).date() >= last_order_from
        ]
    if last_order_to is not None:
        filtered = [
            b
            for b in filtered
            if _as_aware((order_map.get(b.id) or {}).get("last_at"))
            and _as_aware((order_map.get(b.id) or {}).get("last_at")).date() <= last_order_to
        ]
    total = len(filtered)
    page_rows = filtered[(page - 1) * page_size : page * page_size]
    return [_buyer_row(db, b) for b in page_rows], total, counts


def get_buyer(db: Session, ctx: TenantContext, buyer_id: UUID) -> MerchantBuyerDetailOut:
    buyer = (
        db.query(ShopBuyer)
        .filter(uuid_eq(ShopBuyer.id, buyer_id), uuid_eq(ShopBuyer.tenant_id, ctx.tenant_id))
        .first()
    )
    if not buyer:
        raise HTTPException(status_code=404, detail="买家不存在")
    row = _buyer_row(db, buyer)
    return MerchantBuyerDetailOut(**row.model_dump())


def reveal_buyer_mobile(db: Session, ctx: TenantContext, buyer_id: UUID) -> MerchantBuyerDetailOut:
    from app.services.shop.payment_service import write_payment_log

    buyer = (
        db.query(ShopBuyer)
        .filter(uuid_eq(ShopBuyer.id, buyer_id), uuid_eq(ShopBuyer.tenant_id, ctx.tenant_id))
        .first()
    )
    if not buyer:
        raise HTTPException(status_code=404, detail="买家不存在")
    write_payment_log(
        db,
        tenant_id=ctx.tenant_id,
        order_id=None,
        event="reveal_buyer_mobile",
        request_json={"operator_id": str(ctx.user.id), "buyer_id": str(buyer_id)},
        response_json={"buyer_id": str(buyer_id)},
    )
    db.commit()
    row = _buyer_row(db, buyer, reveal=True)
    return MerchantBuyerDetailOut(**row.model_dump())


def export_buyers_csv(
    db: Session,
    ctx: TenantContext,
    *,
    q: str | None = None,
    tab: str | None = None,
    shop_id: UUID | None = None,
    account_status: str | None = None,
    order_count_min: int | None = None,
    entitlement_count_min: int | None = None,
    registered_from: date | None = None,
    registered_to: date | None = None,
    last_order_from: date | None = None,
    last_order_to: date | None = None,
    buyer_ids: list[UUID] | None = None,
) -> str:
    items, total, _ = list_buyers(
        db,
        ctx,
        page=1,
        page_size=5000,
        q=q,
        tab=tab,
        shop_id=shop_id,
        account_status=account_status,
        order_count_min=order_count_min,
        entitlement_count_min=entitlement_count_min,
        registered_from=registered_from,
        registered_to=registered_to,
        last_order_from=last_order_from,
        last_order_to=last_order_to,
        buyer_ids=buyer_ids,
    )
    if total > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    lines = ["手机,昵称,账号状态,来源店铺,订单数,权益数,累计消费(分),注册渠道,最近下单,注册时间"]
    status_label = {"active": "正常", "blocked": "已封禁"}
    for r in items:
        lines.append(
            ",".join(
                [
                    r.mobile_masked or "",
                    (r.nickname or "").replace(",", " "),
                    status_label.get(r.account_status, r.account_status or ""),
                    (r.source_shop_name or "").replace(",", " "),
                    str(r.order_count),
                    str(r.entitlement_count),
                    str(r.paid_amount_cents),
                    r.register_channel,
                    str(r.last_order_at or ""),
                    str(r.created_at or ""),
                ]
            )
        )
    return "\n".join(lines)


def create_buyer_export_task(
    db: Session, ctx: TenantContext, body: BuyerExportRequest | None = None
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or BuyerExportRequest()
    if body.buyer_ids is not None and len(body.buyer_ids) == 0:
        raise HTTPException(status_code=422, detail="请先选择要导出的买家")
    filters = {
        "q": body.q,
        "tab": body.tab,
        "shop_id": str(body.shop_id) if body.shop_id else None,
        "account_status": body.account_status,
        "order_count_min": body.order_count_min,
        "entitlement_count_min": body.entitlement_count_min,
        "registered_from": str(body.registered_from) if body.registered_from else None,
        "registered_to": str(body.registered_to) if body.registered_to else None,
        "last_order_from": str(body.last_order_from) if body.last_order_from else None,
        "last_order_to": str(body.last_order_to) if body.last_order_to else None,
        "buyer_ids": [str(i) for i in body.buyer_ids] if body.buyer_ids else None,
    }
    csv_text = export_buyers_csv(
        db,
        ctx,
        q=body.q,
        tab=body.tab,
        shop_id=body.shop_id,
        account_status=body.account_status,
        order_count_min=body.order_count_min,
        entitlement_count_min=body.entitlement_count_min,
        registered_from=body.registered_from,
        registered_to=body.registered_to,
        last_order_from=body.last_order_from,
        last_order_to=body.last_order_to,
        buyer_ids=body.buyer_ids,
    )
    return export_task_service.persist_csv_task(
        db,
        ctx,
        resource="buyers",
        file_name="shop-buyers.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_buyer_export_task(db: Session, ctx: TenantContext, task_id: UUID) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task(db, ctx, task_id, "buyers")


def read_buyer_export_file(db: Session, ctx: TenantContext, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file(db, ctx, task_id, "buyers")


def list_learning_progress(
    db: Session, ctx: TenantContext, buyer_id: UUID, shop_id: UUID | None = None
) -> BuyerLearningListResponse:
    buyer = (
        db.query(ShopBuyer)
        .filter(uuid_eq(ShopBuyer.id, buyer_id), uuid_eq(ShopBuyer.tenant_id, ctx.tenant_id))
        .first()
    )
    if not buyer:
        raise HTTPException(status_code=404, detail="买家不存在")
    ents_q = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.buyer_id, buyer_id))
    if shop_id:
        ents_q = ents_q.filter(uuid_eq(ShopEntitlement.shop_id, shop_id))
    ents = ents_q.order_by(ShopEntitlement.created_at.desc()).all()
    items: list[BuyerLearningProgressOut] = []
    for e in ents:
        product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, e.product_id)).first()
        if not product or product.type != "course":
            continue
        shop = db.query(ShopStore).filter(uuid_eq(ShopStore.id, e.shop_id)).first()
        prog_rows = (
            db.query(ShopLessonProgress)
            .filter(uuid_eq(ShopLessonProgress.entitlement_id, e.id))
            .all()
        )
        lessons = []
        if product.ref_type == "column" and product.ref_id:
            lessons = (
                db.query(ShopLesson)
                .filter(
                    uuid_eq(ShopLesson.column_id, product.ref_id),
                    ShopLesson.deleted_at.is_(None),
                )
                .all()
            )
        total_lessons = len(lessons) if lessons else len(prog_rows)
        learned = sum(1 for p in prog_rows if (p.progress_pct or 0) >= 100)
        last = max((p.last_learned_at for p in prog_rows if p.last_learned_at), default=None)
        if total_lessons:
            pct_map = {p.lesson_id: (p.progress_pct or 0) for p in prog_rows}
            lesson_ids = [ls.id for ls in lessons] if lessons else [p.lesson_id for p in prog_rows]
            avg = int(sum(pct_map.get(lid, 0) for lid in lesson_ids) / total_lessons)
        else:
            avg = 0
        last_title = None
        if prog_rows:
            latest = max(prog_rows, key=lambda p: p.last_learned_at or p.updated_at or p.created_at)
            lesson = db.query(ShopLesson).filter(uuid_eq(ShopLesson.id, latest.lesson_id)).first()
            last_title = lesson.title if lesson else None
        empty_progress = e.status in ("revoked", "expired") and not prog_rows
        items.append(
            BuyerLearningProgressOut(
                entitlement_id=e.id,
                product_name=product.name if product else None,
                shop_name=shop.name if shop else None,
                entitlement_status=e.status,
                progress_pct=0 if empty_progress else avg,
                learned_count=0 if empty_progress else learned,
                total_lessons=0 if empty_progress else total_lessons,
                last_learned_at=None if empty_progress else last,
                last_lesson_title=None if empty_progress else last_title,
            )
        )
    return BuyerLearningListResponse(items=items, total=len(items))
