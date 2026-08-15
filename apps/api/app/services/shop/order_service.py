"""商城订单 / 支付回调 / 退款 / 权益。对照 PRD 03#o1 #f2 · 执行计划 M5。"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.shop import (
    ShopBuyer,
    ShopEnrollment,
    ShopEntitlement,
    ShopMerchantAccount,
    ShopOrder,
    ShopPayment,
    ShopProduct,
    ShopRefund,
    ShopStore,
)
from app.schemas.shop_platform import (
    CreateOrderResponse,
    EntitlementOut,
    EntitlementExportRequest,
    OrderExportRequest,
    OrderOut,
    OrderRefundRequest,
    OrderTimelineItem,
    PrepayOut,
    RefundOut,
    ShopExportTaskOut,
)
from app.services.shop.buyer_service import mask_mobile
from app.services.shop import payment_service
from app.services.shop.wechat_pay_service import wechat_pay_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gen_order_no() -> str:
    return f"SO{_now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


_CHANNEL_LABEL = {
    "private": "微信",
    "public_douyin": "抖店",
    "public_course_lib": "课程库",
}


def _channel_label(source: str | None) -> str:
    return _CHANNEL_LABEL.get(source or "private", "微信")


def _claim_status(order_status: str, ent: ShopEntitlement | None) -> str | None:
    if order_status == "claim_pending":
        return "pending"
    if ent is None:
        return None
    if ent.status in ("active", "expired", "revoked"):
        return "claimed"
    return "pending"


def _build_timeline(o: ShopOrder, ent: ShopEntitlement | None) -> list[OrderTimelineItem]:
    items: list[OrderTimelineItem] = [
        OrderTimelineItem(at=o.created_at, event="创建订单"),
    ]
    if o.paid_at:
        ch = "微信" if (o.paid_channel or "wxpay") in ("wxpay", "wechat", "stub") else (o.paid_channel or "支付")
        items.append(OrderTimelineItem(at=o.paid_at, event=f"支付成功（{ch}）"))
    if ent and ent.activated_at:
        items.append(OrderTimelineItem(at=ent.activated_at, event="权益开通"))
    if o.status == "claim_pending":
        items.append(OrderTimelineItem(at=o.paid_at or o.updated_at, event="待领权（公域）"))
    if o.status == "refunding":
        items.append(OrderTimelineItem(at=o.updated_at, event="退款处理中"))
    if o.refunded_at:
        items.append(OrderTimelineItem(at=o.refunded_at, event="已退款"))
    if o.status == "closed":
        items.append(OrderTimelineItem(at=o.updated_at, event="订单关闭"))
    return items


def _shops_map(db: Session, shop_ids: set) -> dict:
    ids = {i for i in shop_ids if i is not None}
    if not ids:
        return {}
    rows = db.query(ShopStore).filter(ShopStore.id.in_(list(ids))).all()
    return {s.id: s for s in rows}


def _order_out(
    o: ShopOrder,
    *,
    reveal_mobile: bool = False,
    buyer: ShopBuyer | None = None,
    entitlement: ShopEntitlement | None = None,
    with_detail: bool = False,
    shop: ShopStore | None = None,
) -> OrderOut:
    snap = o.product_snapshot_json or {}
    mobile = o.buyer_mobile_snapshot
    nick = None
    if buyer is not None:
        nick = buyer.nickname
        if not mobile:
            mobile = buyer.mobile
    external = snap.get("external_order_no") or None
    if not external and o.source and o.source.startswith("public") and o.wx_transaction_id:
        external = o.wx_transaction_id
    out = OrderOut(
        id=o.id,
        tenant_id=o.tenant_id,
        shop_id=o.shop_id,
        buyer_id=o.buyer_id,
        product_id=o.product_id,
        order_no=o.order_no,
        type=o.type,
        amount_cents=o.amount_cents,
        status=o.status,
        paid_amount_cents=o.paid_amount_cents,
        paid_at=o.paid_at,
        paid_channel=o.paid_channel,
        refund_amount_cents=o.refund_amount_cents,
        refunded_at=o.refunded_at,
        refund_reason=o.refund_reason,
        needs_red_flush=bool(o.needs_red_flush),
        invoice_status=o.invoice_status or "none",
        source=o.source,
        channel=_channel_label(o.source),
        buyer_nickname=nick,
        buyer_mobile=mobile if reveal_mobile else None,
        buyer_mobile_masked=mask_mobile(mobile),
        external_order_no=external,
        product_name=snap.get("name"),
        shop_name=shop.name if shop else None,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )
    if with_detail:
        out.entitlement_id = entitlement.id if entitlement else None
        out.entitlement_status = entitlement.status if entitlement else None
        out.entitlement_expires_at = entitlement.expires_at if entitlement else None
        out.claim_status = _claim_status(o.status, entitlement)
        out.timeline = _build_timeline(o, entitlement)
    return out


def _buyers_map(db: Session, buyer_ids: set) -> dict:
    if not buyer_ids:
        return {}
    rows = db.query(ShopBuyer).filter(ShopBuyer.id.in_(list(buyer_ids))).all()
    return {b.id: b for b in rows}


def _entitlement_out(
    e: ShopEntitlement,
    product: ShopProduct | None = None,
    *,
    service_mode: str | None = None,
    buyer: ShopBuyer | None = None,
    order: ShopOrder | None = None,
    shop: ShopStore | None = None,
) -> EntitlementOut:
    service_offer_id = None
    if product and product.ref_type == "service_offer" and product.ref_id:
        service_offer_id = product.ref_id
    return EntitlementOut(
        id=e.id,
        tenant_id=e.tenant_id,
        buyer_id=e.buyer_id,
        order_id=e.order_id,
        product_id=e.product_id,
        shop_id=e.shop_id,
        status=e.status,
        activated_at=e.activated_at,
        revoked_at=e.revoked_at,
        revoke_reason=e.revoke_reason,
        remaining_count=e.remaining_count,
        total_count=e.total_count,
        verify_code=e.verify_code,
        expires_at=e.expires_at,
        product_name=product.name if product else None,
        product_type=product.type if product else None,
        service_offer_id=service_offer_id,
        service_mode=service_mode,
        created_at=e.created_at,
        buyer_nickname=buyer.nickname if buyer else None,
        buyer_mobile_masked=mask_mobile(buyer.mobile) if buyer else None,
        order_no=order.order_no if order else None,
        shop_name=shop.name if shop else None,
    )


def _refund_out(r: ShopRefund, order: ShopOrder | None = None) -> RefundOut:
    return RefundOut(
        id=r.id,
        order_id=r.order_id,
        tenant_id=r.tenant_id,
        amount_cents=r.amount_cents,
        reason=r.reason,
        status=r.status,
        initiated_by=r.initiated_by,
        is_partial=bool(r.is_partial),
        needs_red_flush=bool(order.needs_red_flush) if order else False,
        entitlement_revoked_at=r.entitlement_revoked_at,
        processed_at=r.processed_at,
        created_at=r.created_at,
    )


def _assert_trade_allowed(db: Session, tenant_id: UUID) -> ShopMerchantAccount:
    m = db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant_id)).first()
    if not m:
        raise HTTPException(status_code=409, detail="商家未入驻")
    if m.status == "suspended":
        raise HTTPException(status_code=409, detail="暂停营业，暂不可下单")
    if m.status == "closed":
        raise HTTPException(status_code=409, detail="商家已清退")
    return m


def create_order(
    db: Session,
    buyer: ShopBuyer,
    product_id: UUID,
    *,
    client_amount_cents: int | None = None,
) -> CreateOrderResponse:
    if not buyer.mobile:
        raise HTTPException(status_code=422, detail="请先绑定手机号")
    _assert_trade_allowed(db, buyer.tenant_id)
    product = (
        db.query(ShopProduct)
        .filter(
            uuid_eq(ShopProduct.id, product_id),
            uuid_eq(ShopProduct.tenant_id, buyer.tenant_id),
            ShopProduct.deleted_at.is_(None),
        )
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    if product.status != "on_sale":
        raise HTTPException(status_code=409, detail="商品未上架，不可下单")
    store = db.query(ShopStore).filter(uuid_eq(ShopStore.id, product.shop_id)).first()
    if not store or store.status == "closed":
        raise HTTPException(status_code=409, detail="店铺不可用")
    if store.status == "paused":
        raise HTTPException(status_code=403, detail="店铺暂停营业")

    sku_price = int(product.price_cents or 0)
    if client_amount_cents is not None and int(client_amount_cents) != sku_price:
        raise HTTPException(status_code=422, detail="金额与商品价格不一致，已以后端为准拒绝")

    cfg = payment_service.require_active_config(db, buyer.tenant_id, product.shop_id)
    api_key = payment_service.get_api_key(cfg)

    order = ShopOrder(
        id=uuid.uuid4(),
        tenant_id=buyer.tenant_id,
        shop_id=product.shop_id,
        buyer_id=buyer.id,
        product_id=product.id,
        product_snapshot_json={
            "id": str(product.id),
            "name": product.name,
            "type": product.type,
            "price_cents": product.price_cents,
            "refund_policy": product.refund_policy,
            "ref_type": product.ref_type,
            "ref_id": str(product.ref_id) if product.ref_id else None,
            "extra": product.extra or {},
        },
        order_no=_gen_order_no(),
        type=product.type,
        amount_cents=sku_price,
        status="pending_payment",
        source="private",
        buyer_mobile_snapshot=buyer.mobile,
    )
    db.add(order)
    db.flush()

    payment = ShopPayment(
        id=uuid.uuid4(),
        order_id=order.id,
        tenant_id=order.tenant_id,
        shop_id=order.shop_id,
        amount_cents=sku_price,
        status="pending",
    )
    db.add(payment)
    db.flush()

    try:
        prepay_raw = wechat_pay_service.create_prepay(
            order_no=order.order_no,
            amount_cents=sku_price,
            description=(product.name or "商城商品")[:120],
            openid=buyer.wx_openid,
            wx_app_id=cfg.wx_app_id,
            wx_mch_id=cfg.wx_mch_id,
            api_key=api_key,
            notify_url=cfg.wx_notify_url,
        )
    except NotImplementedError as e:
        payment_service.write_payment_log(
            db,
            tenant_id=order.tenant_id,
            order_id=order.id,
            event="prepay",
            status="error",
            error_msg=str(e),
        )
        db.commit()
        raise HTTPException(status_code=503, detail=str(e)) from e

    payment.prepay_id = prepay_raw.get("prepay_id")
    payment_service.write_payment_log(
        db,
        tenant_id=order.tenant_id,
        order_id=order.id,
        event="prepay",
        request_json={"order_no": order.order_no, "amount_cents": sku_price},
        response_json={"prepay_id": payment.prepay_id, "mode": prepay_raw.get("mode")},
    )
    payment_service.write_payment_log(
        db,
        tenant_id=order.tenant_id,
        order_id=order.id,
        event="create",
        request_json={"product_id": str(product_id)},
        response_json={"order_id": str(order.id), "order_no": order.order_no},
    )
    db.commit()
    db.refresh(order)
    db.refresh(payment)
    prepay = PrepayOut(
        mode=str(prepay_raw.get("mode") or "stub"),
        prepay_id=str(prepay_raw.get("prepay_id")),
        appId=prepay_raw.get("appId"),
        timeStamp=prepay_raw.get("timeStamp"),
        nonceStr=prepay_raw.get("nonceStr"),
        package=prepay_raw.get("package"),
        signType=prepay_raw.get("signType"),
        paySign=prepay_raw.get("paySign"),
        mch_id=prepay_raw.get("mch_id"),
    )
    return CreateOrderResponse(order=_order_out(order), prepay=prepay, payment_id=payment.id)


def _activate_entitlement_for_order(db: Session, order: ShopOrder) -> None:
    existing = (
        db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.order_id, order.id)).first()
    )
    if existing:
        return
    snap = order.product_snapshot_json or {}
    extra = snap.get("extra") or {}
    total_count = None
    remaining = None
    if order.type == "service":
        total_count = int(extra.get("service_times") or extra.get("total_count") or 1)
        remaining = total_count
        # A07 关联服务：次数卡取 offer.total_times；预约模式可无次数（按次核销仍给 1）
        if snap.get("ref_type") == "service_offer" and snap.get("ref_id"):
            from app.models.shop import ShopServiceOffer

            offer = (
                db.query(ShopServiceOffer)
                .filter(uuid_eq(ShopServiceOffer.id, UUID(str(snap["ref_id"]))))
                .first()
            )
            if offer:
                if offer.mode == "times_card" and offer.total_times:
                    total_count = int(offer.total_times)
                    remaining = total_count
                elif offer.mode == "booking":
                    total_count = int(offer.total_times or extra.get("service_times") or 1)
                    remaining = total_count
    verify_code = None
    if order.type == "service":
        # PRD A08：买家出示 6 位核销码
        verify_code = f"{uuid.uuid4().int % 10**6:06d}"
    ent = ShopEntitlement(
        id=uuid.uuid4(),
        tenant_id=order.tenant_id,
        buyer_id=order.buyer_id,
        order_id=order.id,
        product_id=order.product_id,
        shop_id=order.shop_id,
        status="active",
        activated_at=_now(),
        remaining_count=remaining,
        total_count=total_count,
        verify_code=verify_code,
    )
    db.add(ent)
    db.flush()
    if order.type == "course":
        course_id = UUID(snap["ref_id"]) if snap.get("ref_id") else order.product_id
        db.add(
            ShopEnrollment(
                id=uuid.uuid4(),
                tenant_id=order.tenant_id,
                buyer_id=order.buyer_id,
                entitlement_id=ent.id,
                course_id=course_id,
                status="active",
                progress_json={},
            )
        )
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, order.product_id)).first()
    if product:
        product.sales_count = int(product.sales_count or 0) + 1


def apply_payment_notify(
    db: Session,
    *,
    order_no: str,
    transaction_id: str,
    paid_amount_cents: int | None = None,
    sign: str | None = None,
    skip_sign: bool = False,
) -> OrderOut:
    order = db.query(ShopOrder).filter(ShopOrder.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    cfg = payment_service.get_active_config(db, order.tenant_id, order.shop_id)
    api_key = payment_service.get_api_key(cfg) if cfg else "mock_api_key_001"
    amount = int(paid_amount_cents) if paid_amount_cents is not None else int(order.amount_cents)

    # 幂等：已支付且同 transaction — 仍验签（坏签不改状态）
    if not skip_sign:
        verified = wechat_pay_service.verify_notify(
            order_no=order_no,
            transaction_id=transaction_id,
            paid_amount_cents=amount,
            sign=sign,
            api_key=api_key,
        )
        if verified is None:
            payment_service.write_payment_log(
                db,
                tenant_id=order.tenant_id,
                order_id=order.id,
                event="notify",
                request_json={
                    "order_no": order_no,
                    "transaction_id": transaction_id,
                    "paid_amount_cents": amount,
                    "sign": sign,
                },
                status="error",
                error_msg="签名校验失败",
                wx_transaction_id=transaction_id,
            )
            db.commit()
            raise HTTPException(status_code=400, detail="签名校验失败")

    if amount != int(order.amount_cents):
        payment_service.write_payment_log(
            db,
            tenant_id=order.tenant_id,
            order_id=order.id,
            event="notify",
            request_json={"paid_amount_cents": amount, "order_amount": order.amount_cents},
            status="error",
            error_msg="金额不符",
            wx_transaction_id=transaction_id,
        )
        db.commit()
        raise HTTPException(status_code=422, detail="支付金额与订单不符")

    # 幂等：已支付且同 transaction
    if order.status == "paid" and order.wx_transaction_id == transaction_id:
        payment_service.write_payment_log(
            db,
            tenant_id=order.tenant_id,
            order_id=order.id,
            event="notify",
            response_json={"idempotent": True},
            status="ok",
            wx_transaction_id=transaction_id,
        )
        db.commit()
        return _order_out(order)
    if order.status in ("refunded", "refunding", "closed"):
        raise HTTPException(status_code=409, detail=f"订单状态为 {order.status}，不可支付")
    if order.status == "paid" and order.wx_transaction_id and order.wx_transaction_id != transaction_id:
        raise HTTPException(status_code=409, detail="订单已支付")

    if transaction_id:
        dup = (
            db.query(ShopOrder)
            .filter(ShopOrder.wx_transaction_id == transaction_id, ShopOrder.id != order.id)
            .first()
        )
        if dup:
            raise HTTPException(status_code=409, detail="transaction_id 已使用")

    order.status = "paid"
    order.paid_amount_cents = amount
    order.paid_at = _now()
    order.paid_channel = "wxpay"
    order.wx_transaction_id = transaction_id

    pay = db.query(ShopPayment).filter(uuid_eq(ShopPayment.order_id, order.id)).first()
    if pay:
        pay.status = "success"
        pay.wx_transaction_id = transaction_id
        pay.paid_at = order.paid_at
        pay.amount_cents = amount

    _activate_entitlement_for_order(db, order)

    payment_service.write_payment_log(
        db,
        tenant_id=order.tenant_id,
        order_id=order.id,
        event="notify",
        request_json={"order_no": order_no, "transaction_id": transaction_id, "amount": amount},
        response_json={"order_status": "paid"},
        status="ok",
        wx_transaction_id=transaction_id,
    )
    db.commit()
    db.refresh(order)
    return _order_out(order)


def query_and_sync_payment(db: Session, buyer: ShopBuyer, order_id: UUID) -> OrderOut:
    """主动查单兜底：pending → paid。"""
    order = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.id, order_id), uuid_eq(ShopOrder.buyer_id, buyer.id))
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == "paid":
        return _order_out(order)
    if order.status != "pending_payment":
        raise HTTPException(status_code=422, detail=f"订单状态为 {order.status}，不可查单补偿")

    cfg = payment_service.require_active_config(db, order.tenant_id, order.shop_id)
    q = wechat_pay_service.query_order(order_no=order.order_no, amount_cents=order.amount_cents)
    payment_service.write_payment_log(
        db,
        tenant_id=order.tenant_id,
        order_id=order.id,
        event="query",
        response_json=q,
    )
    db.commit()
    if q.get("trade_state") != "SUCCESS":
        return _order_out(order)

    tx = q.get("transaction_id") or f"QRY{uuid.uuid4().hex[:16]}"
    from app.services.shop.wechat_pay_service import stub_sign

    sign = stub_sign(order.order_no, tx, int(order.amount_cents), payment_service.get_api_key(cfg))
    return apply_payment_notify(
        db,
        order_no=order.order_no,
        transaction_id=tx,
        paid_amount_cents=int(order.amount_cents),
        sign=sign,
    )


_ORDER_SORT_COLS = {
    "no": ShopOrder.order_no,
    "order_no": ShopOrder.order_no,
    "amount": ShopOrder.amount_cents,
    "status": ShopOrder.status,
    "ordered_at": ShopOrder.created_at,
    "created_at": ShopOrder.created_at,
    "channel": ShopOrder.source,
}


def _merchant_order_query(
    db: Session,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    q: str | None = None,
    source: str | None = None,
    product_type: str | None = None,
    amount_min: int | None = None,
    amount_max: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    external_order_no: str | None = None,
    shop_id: UUID | None = None,
):
    query = db.query(ShopOrder).filter(uuid_eq(ShopOrder.tenant_id, tenant_id))
    if shop_id:
        query = query.filter(uuid_eq(ShopOrder.shop_id, shop_id))
    if status_filter:
        query = query.filter(ShopOrder.status == status_filter)
    if source:
        query = query.filter(ShopOrder.source == source)
    if product_type:
        query = query.filter(ShopOrder.type == product_type)
    if amount_min is not None:
        query = query.filter(ShopOrder.amount_cents >= amount_min)
    if amount_max is not None:
        query = query.filter(ShopOrder.amount_cents <= amount_max)
    if created_from is not None:
        query = query.filter(ShopOrder.created_at >= created_from)
    if created_to is not None:
        query = query.filter(ShopOrder.created_at <= created_to)
    if external_order_no:
        like_ext = f"%{external_order_no}%"
        query = query.filter(ShopOrder.wx_transaction_id.ilike(like_ext))
    if q:
        like = f"%{q}%"
        nick_hit = (
            db.query(ShopBuyer.id)
            .filter(ShopBuyer.id == ShopOrder.buyer_id, ShopBuyer.nickname.ilike(like))
            .exists()
        )
        query = query.filter(
            (ShopOrder.order_no.ilike(like))
            | (ShopOrder.buyer_mobile_snapshot.ilike(like))
            | (ShopOrder.wx_transaction_id.ilike(like))
            | nick_hit
            | cast(ShopOrder.product_snapshot_json, String).ilike(like)
        )
    return query


def order_status_counts(
    db: Session, tenant_id: UUID, *, shop_id: UUID | None = None
) -> dict[str, int]:
    from sqlalchemy import func

    q = db.query(ShopOrder.status, func.count(ShopOrder.id)).filter(
        uuid_eq(ShopOrder.tenant_id, tenant_id)
    )
    if shop_id:
        q = q.filter(uuid_eq(ShopOrder.shop_id, shop_id))
    rows = q.group_by(ShopOrder.status).all()
    counts = {s: int(c) for s, c in rows}
    counts["all"] = sum(counts.values())
    return counts


def list_merchant_orders(
    db: Session,
    ctx: TenantContext,
    *,
    status_filter: str | None,
    q: str | None,
    page: int,
    page_size: int,
    reveal_mobile: bool = False,
    source: str | None = None,
    product_type: str | None = None,
    amount_min: int | None = None,
    amount_max: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    external_order_no: str | None = None,
    buyer_id: UUID | None = None,
    shop_id: UUID | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> tuple[list[OrderOut], int, dict[str, int]]:
    query = _merchant_order_query(
        db,
        ctx.tenant_id,
        status_filter=status_filter,
        q=q,
        source=source,
        product_type=product_type,
        amount_min=amount_min,
        amount_max=amount_max,
        created_from=created_from,
        created_to=created_to,
        external_order_no=external_order_no,
        shop_id=shop_id,
    )
    if buyer_id:
        query = query.filter(uuid_eq(ShopOrder.buyer_id, buyer_id))
    total = query.count()
    col = _ORDER_SORT_COLS.get(sort_by or "", ShopOrder.created_at)
    if sort_by == "buyer":
        query = query.outerjoin(ShopBuyer, ShopBuyer.id == ShopOrder.buyer_id)
        col = ShopBuyer.nickname
    elif sort_by == "product":
        col = cast(ShopOrder.product_snapshot_json, String)
    order_clause = col.asc() if (sort_dir or "").lower() == "asc" else col.desc()
    rows = (
        query.order_by(order_clause, ShopOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    buyers = _buyers_map(db, {o.buyer_id for o in rows})
    shops = _shops_map(db, {o.shop_id for o in rows})
    items = [
        _order_out(
            o,
            reveal_mobile=reveal_mobile,
            buyer=buyers.get(o.buyer_id),
            shop=shops.get(o.shop_id),
        )
        for o in rows
    ]
    return items, total, order_status_counts(db, ctx.tenant_id, shop_id=shop_id)


_ORDER_STATUS_ZH = {
    "pending_payment": "待付款",
    "paid": "已付款",
    "claim_pending": "待领权",
    "refunding": "退款中",
    "refunded": "已退款",
    "closed": "已关闭",
}

_ORDER_CSV_COL_MAP = {
    "order_no": ["单号"],
    "product_name": ["商品"],
    "buyer": ["买家昵称", "买家手机"],
    "amount": ["金额(分)"],
    "channel": ["渠道"],
    "status": ["状态"],
    "external_order_no": ["外部单号"],
    "created_at": ["下单时间"],
    "paid_at": ["支付时间"],
}
_ORDER_CSV_ALL_HEADERS = [
    "单号",
    "商品",
    "买家昵称",
    "买家手机",
    "金额(分)",
    "渠道",
    "状态",
    "外部单号",
    "下单时间",
    "支付时间",
]


def _order_csv_headers(columns: list[str] | None) -> list[str]:
    if not columns:
        return list(_ORDER_CSV_ALL_HEADERS)
    headers: list[str] = []
    seen: set[str] = set()
    for key in columns:
        for h in _ORDER_CSV_COL_MAP.get(key, []):
            if h not in seen:
                seen.add(h)
                headers.append(h)
    return headers or list(_ORDER_CSV_ALL_HEADERS)


def export_merchant_orders_csv(
    db: Session,
    ctx: TenantContext,
    *,
    status_filter: str | None = None,
    q: str | None = None,
    source: str | None = None,
    shop_id: UUID | None = None,
    product_type: str | None = None,
    amount_min: int | None = None,
    amount_max: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    external_order_no: str | None = None,
    columns: list[str] | None = None,
) -> str:
    import csv
    import io

    query = _merchant_order_query(
        db,
        ctx.tenant_id,
        status_filter=status_filter,
        q=q,
        source=source,
        shop_id=shop_id,
        product_type=product_type,
        amount_min=amount_min,
        amount_max=amount_max,
        created_from=created_from,
        created_to=created_to,
        external_order_no=external_order_no,
    )
    total = query.count()
    if total > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    rows = query.order_by(ShopOrder.created_at.desc()).all()
    buyers = _buyers_map(db, {o.buyer_id for o in rows})
    headers = _order_csv_headers(columns)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for o in rows:
        b = buyers.get(o.buyer_id)
        out = _order_out(o, buyer=b)
        values = {
            "单号": out.order_no,
            "商品": out.product_name or "",
            "买家昵称": out.buyer_nickname or "",
            "买家手机": out.buyer_mobile_masked or "",
            "金额(分)": out.amount_cents,
            "渠道": out.channel,
            "状态": _ORDER_STATUS_ZH.get(out.status, out.status),
            "外部单号": out.external_order_no or "",
            "下单时间": out.created_at.isoformat() if out.created_at else "",
            "支付时间": out.paid_at.isoformat() if out.paid_at else "",
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_order_export_task(
    db: Session, ctx: TenantContext, body: OrderExportRequest | None = None
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or OrderExportRequest()
    filters = {
        "status": body.status,
        "q": body.q,
        "source": body.source,
        "shop_id": str(body.shop_id) if body.shop_id else None,
        "product_type": body.product_type,
        "amount_min": body.amount_min,
        "amount_max": body.amount_max,
        "created_from": str(body.created_from) if body.created_from else None,
        "created_to": str(body.created_to) if body.created_to else None,
        "external_order_no": body.external_order_no,
        "columns": body.columns,
    }
    csv_text = export_merchant_orders_csv(
        db,
        ctx,
        status_filter=body.status,
        q=body.q,
        source=body.source,
        shop_id=body.shop_id,
        product_type=body.product_type,
        amount_min=body.amount_min,
        amount_max=body.amount_max,
        created_from=body.created_from,
        created_to=body.created_to,
        external_order_no=body.external_order_no,
        columns=body.columns,
    )
    return export_task_service.persist_csv_task(
        db,
        ctx,
        resource="orders",
        file_name="shop-orders.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_order_export_task(db: Session, ctx: TenantContext, task_id: UUID) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task(db, ctx, task_id, "orders")


def read_order_export_file(db: Session, ctx: TenantContext, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file(db, ctx, task_id, "orders")


def list_buyer_orders(
    db: Session,
    buyer: ShopBuyer,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
) -> tuple[list[OrderOut], int]:
    query = db.query(ShopOrder).filter(uuid_eq(ShopOrder.buyer_id, buyer.id))
    if status:
        # M11 Tab「退款」= 退款中 + 已退款
        if status == "refund":
            query = query.filter(ShopOrder.status.in_(("refunding", "refunded")))
        else:
            query = query.filter(ShopOrder.status == status)
    total = query.count()
    rows = (
        query.order_by(ShopOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [_order_out(o, buyer=buyer) for o in rows], total


def get_merchant_order(db: Session, ctx: TenantContext, order_id: UUID) -> OrderOut:
    o = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.id, order_id), uuid_eq(ShopOrder.tenant_id, ctx.tenant_id))
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    buyer = db.query(ShopBuyer).filter(uuid_eq(ShopBuyer.id, o.buyer_id)).first()
    ent = (
        db.query(ShopEntitlement)
        .filter(uuid_eq(ShopEntitlement.order_id, o.id))
        .first()
    )
    shop = db.query(ShopStore).filter(uuid_eq(ShopStore.id, o.shop_id)).first()
    return _order_out(
        o, reveal_mobile=False, buyer=buyer, entitlement=ent, with_detail=True, shop=shop
    )


def reveal_order_mobile(db: Session, ctx: TenantContext, order_id: UUID) -> OrderOut:
    """买家手机明文揭露：须 shop.buyer.view（路由层校验）+ 留痕。"""
    from app.services.shop.payment_service import write_payment_log

    o = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.id, order_id), uuid_eq(ShopOrder.tenant_id, ctx.tenant_id))
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    buyer = db.query(ShopBuyer).filter(uuid_eq(ShopBuyer.id, o.buyer_id)).first()
    write_payment_log(
        db,
        tenant_id=ctx.tenant_id,
        order_id=o.id,
        event="reveal_mobile",
        request_json={"operator_id": str(ctx.user.id)},
        response_json={"order_id": str(o.id)},
    )
    db.commit()
    ent = (
        db.query(ShopEntitlement)
        .filter(uuid_eq(ShopEntitlement.order_id, o.id))
        .first()
    )
    shop = db.query(ShopStore).filter(uuid_eq(ShopStore.id, o.shop_id)).first()
    return _order_out(
        o, reveal_mobile=True, buyer=buyer, entitlement=ent, with_detail=True, shop=shop
    )


def close_order(db: Session, ctx: TenantContext, order_id: UUID, reason: str | None) -> OrderOut:
    o = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.id, order_id), uuid_eq(ShopOrder.tenant_id, ctx.tenant_id))
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    if o.status != "pending_payment":
        raise HTTPException(status_code=422, detail="仅待付款订单可关闭")
    o.status = "closed"
    o.refund_reason = reason or "商家关闭"
    db.commit()
    db.refresh(o)
    buyer = db.query(ShopBuyer).filter(uuid_eq(ShopBuyer.id, o.buyer_id)).first()
    return _order_out(o, buyer=buyer)


def resend_claim_notify(db: Session, ctx: TenantContext, order_id: UUID, remark: str | None) -> dict:
    from app.services.shop.payment_service import write_payment_log

    o = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.id, order_id), uuid_eq(ShopOrder.tenant_id, ctx.tenant_id))
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    if o.status != "claim_pending":
        raise HTTPException(status_code=422, detail="仅待领权订单可重发短信")
    write_payment_log(
        db,
        tenant_id=ctx.tenant_id,
        order_id=o.id,
        event="resend_claim_notify",
        request_json={"remark": remark, "operator_id": str(ctx.user.id)},
        response_json={"ok": True},
    )
    db.commit()
    return {"ok": True, "order_id": str(o.id), "status": o.status}


def get_buyer_order(db: Session, buyer: ShopBuyer, order_id: UUID) -> OrderOut:
    o = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.id, order_id), uuid_eq(ShopOrder.buyer_id, buyer.id))
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    ent = (
        db.query(ShopEntitlement)
        .filter(uuid_eq(ShopEntitlement.order_id, o.id))
        .first()
    )
    return _order_out(o, buyer=buyer, entitlement=ent, with_detail=True)


def buyer_cancel_order(db: Session, buyer: ShopBuyer, order_id: UUID) -> OrderOut:
    """M12-B：买家取消待付款订单。"""
    o = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.id, order_id), uuid_eq(ShopOrder.buyer_id, buyer.id))
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    if o.status != "pending_payment":
        raise HTTPException(status_code=422, detail="仅待付款可取消")
    o.status = "closed"
    o.refund_reason = "买家取消"
    db.commit()
    db.refresh(o)
    return _order_out(o, buyer=buyer, with_detail=True)


def buyer_continue_pay(db: Session, buyer: ShopBuyer, order_id: UUID) -> CreateOrderResponse:
    """M11/M12 去支付：待付款单续拉预支付；stub 模式直接完成支付便于联调。"""
    from app.services.shop.wechat_pay_service import stub_sign

    o = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.id, order_id), uuid_eq(ShopOrder.buyer_id, buyer.id))
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    if o.status == "closed":
        raise HTTPException(status_code=422, detail="订单已关闭")
    if o.status != "pending_payment":
        raise HTTPException(status_code=422, detail="当前状态不可支付")

    product = (
        db.query(ShopProduct)
        .filter(uuid_eq(ShopProduct.id, o.product_id), ShopProduct.deleted_at.is_(None))
        .first()
    )
    if not product or product.status != "on_sale":
        raise HTTPException(status_code=422, detail="商品已下架")

    cfg = payment_service.require_active_config(db, buyer.tenant_id, o.shop_id)
    api_key = payment_service.get_api_key(cfg)
    amount = int(o.amount_cents or 0)
    payment = db.query(ShopPayment).filter(uuid_eq(ShopPayment.order_id, o.id)).first()
    if not payment:
        payment = ShopPayment(
            id=uuid.uuid4(),
            order_id=o.id,
            tenant_id=o.tenant_id,
            shop_id=o.shop_id,
            amount_cents=amount,
            status="pending",
        )
        db.add(payment)
        db.flush()

    try:
        prepay_raw = wechat_pay_service.create_prepay(
            order_no=o.order_no,
            amount_cents=amount,
            description=(o.product_snapshot_json or {}).get("name") or "商城商品",
            openid=buyer.wx_openid,
            wx_app_id=cfg.wx_app_id,
            wx_mch_id=cfg.wx_mch_id,
            api_key=api_key,
            notify_url=cfg.wx_notify_url,
        )
    except NotImplementedError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    payment.prepay_id = prepay_raw.get("prepay_id")
    payment_service.write_payment_log(
        db,
        tenant_id=o.tenant_id,
        order_id=o.id,
        event="continue_prepay",
        request_json={"order_no": o.order_no},
        response_json={"prepay_id": payment.prepay_id, "mode": prepay_raw.get("mode")},
    )
    db.commit()
    db.refresh(o)
    db.refresh(payment)

    mode = str(prepay_raw.get("mode") or "stub")
    if mode == "stub":
        tx = f"TX{uuid.uuid4().hex[:16]}"
        sign = stub_sign(o.order_no, tx, amount, api_key)
        paid = apply_payment_notify(
            db,
            order_no=o.order_no,
            transaction_id=tx,
            paid_amount_cents=amount,
            sign=sign,
        )
        return CreateOrderResponse(order=paid, prepay=None, payment_id=payment.id)

    prepay = PrepayOut(
        mode=mode,
        prepay_id=str(prepay_raw.get("prepay_id")),
        appId=prepay_raw.get("appId"),
        timeStamp=prepay_raw.get("timeStamp"),
        nonceStr=prepay_raw.get("nonceStr"),
        package=prepay_raw.get("package"),
        signType=prepay_raw.get("signType"),
        paySign=prepay_raw.get("paySign"),
        mch_id=prepay_raw.get("mch_id"),
    )
    return CreateOrderResponse(
        order=_order_out(o, buyer=buyer, with_detail=True),
        prepay=prepay,
        payment_id=payment.id,
    )


def list_buyer_order_refunds(
    db: Session, buyer: ShopBuyer, order_id: UUID
) -> list[RefundOut]:
    o = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.id, order_id), uuid_eq(ShopOrder.buyer_id, buyer.id))
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    rows = (
        db.query(ShopRefund)
        .filter(uuid_eq(ShopRefund.order_id, o.id))
        .order_by(ShopRefund.created_at.desc())
        .all()
    )
    return [_refund_out(r, o) for r in rows]


def mark_invoice(db: Session, ctx: TenantContext, order_id: UUID, invoice_status: str) -> OrderOut:
    o = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.id, order_id), uuid_eq(ShopOrder.tenant_id, ctx.tenant_id))
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    if invoice_status not in ("none", "submitted", "issued"):
        raise HTTPException(status_code=422, detail="invoice_status 无效")
    o.invoice_status = invoice_status
    db.commit()
    db.refresh(o)
    buyer = db.query(ShopBuyer).filter(uuid_eq(ShopBuyer.id, o.buyer_id)).first()
    return _order_out(o, buyer=buyer)


def _complete_refund_success(db: Session, order: ShopOrder, refund: ShopRefund) -> None:
    now = _now()
    order.status = "refunded"
    order.refund_amount_cents = refund.amount_cents
    order.refunded_at = now
    order.refund_reason = refund.reason
    if order.invoice_status == "issued":
        order.needs_red_flush = True
        from app.models.shop import ShopInvoiceRequest

        for inv in (
            db.query(ShopInvoiceRequest)
            .filter(
                uuid_eq(ShopInvoiceRequest.order_id, order.id),
                ShopInvoiceRequest.status == "issued",
            )
            .all()
        ):
            inv.needs_red_flush = True

    ent = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.order_id, order.id)).first()
    if ent and ent.status != "revoked":
        ent.status = "revoked"
        ent.revoked_at = now
        ent.revoke_reason = refund.reason or "退款撤销"
        refund.entitlement_revoked_at = now
        for enr in (
            db.query(ShopEnrollment)
            .filter(uuid_eq(ShopEnrollment.entitlement_id, ent.id), ShopEnrollment.status == "active")
            .all()
        ):
            enr.status = "revoked"

    refund.status = "succeeded"
    refund.processed_at = now
    refund.wx_refund_id = refund.wx_refund_id or f"RF{uuid.uuid4().hex[:16]}"


def initiate_refund(
    db: Session,
    order: ShopOrder,
    *,
    body: OrderRefundRequest,
    initiated_by: str,
    operator_id: UUID | None = None,
) -> RefundOut:
    if order.status == "refunding":
        raise HTTPException(status_code=409, detail="退款进行中")
    if order.status == "refunded":
        raise HTTPException(status_code=409, detail="订单已退款")
    if order.status != "paid":
        raise HTTPException(status_code=422, detail="仅已付款订单可退款")

    paid = int(order.paid_amount_cents or order.amount_cents or 0)
    amount = int(body.amount_cents) if body.amount_cents is not None else paid
    if amount < paid:
        raise HTTPException(status_code=422, detail="Phase1 仅支持全额退款")
    if amount > paid:
        raise HTTPException(status_code=422, detail="退款金额不可超过实付")

    # 进行中互斥
    inflight = (
        db.query(ShopRefund)
        .filter(
            uuid_eq(ShopRefund.order_id, order.id),
            ShopRefund.status == "processing",
        )
        .first()
    )
    if inflight:
        raise HTTPException(status_code=409, detail="已有进行中的退款")

    refund = ShopRefund(
        id=uuid.uuid4(),
        order_id=order.id,
        tenant_id=order.tenant_id,
        amount_cents=amount,
        reason=body.reason,
        status="processing",
        initiated_by=initiated_by,
        operator_id=operator_id,
        is_partial=False,
    )
    order.status = "refunding"
    db.add(refund)
    db.flush()

    # Phase1 stub：同步成功（真实微信退款在 M3）
    _complete_refund_success(db, order, refund)
    db.commit()
    db.refresh(refund)
    db.refresh(order)
    return _refund_out(refund, order)


def merchant_refund(
    db: Session, ctx: TenantContext, order_id: UUID, body: OrderRefundRequest
) -> RefundOut:
    o = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.id, order_id), uuid_eq(ShopOrder.tenant_id, ctx.tenant_id))
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    return initiate_refund(
        db, o, body=body, initiated_by="merchant", operator_id=ctx.user.id
    )


def buyer_refund(db: Session, buyer: ShopBuyer, order_id: UUID, body: OrderRefundRequest) -> RefundOut:
    o = (
        db.query(ShopOrder)
        .filter(uuid_eq(ShopOrder.id, order_id), uuid_eq(ShopOrder.buyer_id, buyer.id))
        .first()
    )
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    snap = o.product_snapshot_json or {}
    policy = snap.get("refund_policy") or "before_fulfill"
    if policy == "manual_only":
        raise HTTPException(status_code=422, detail="该商品仅支持商家人工退款")
    return initiate_refund(db, o, body=body, initiated_by="buyer")


def list_refunds(
    db: Session, ctx: TenantContext, *, page: int, page_size: int
) -> tuple[list[RefundOut], int]:
    query = db.query(ShopRefund).filter(uuid_eq(ShopRefund.tenant_id, ctx.tenant_id))
    total = query.count()
    rows = (
        query.order_by(ShopRefund.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    order_ids = {r.order_id for r in rows}
    orders = {
        o.id: o
        for o in db.query(ShopOrder).filter(ShopOrder.id.in_(list(order_ids))).all()
    } if order_ids else {}
    return [_refund_out(r, orders.get(r.order_id)) for r in rows], total


def _not_consumed():
    return or_(ShopEntitlement.remaining_count.is_(None), ShopEntitlement.remaining_count > 0)


def _date_start(d: date) -> datetime:
    return datetime.combine(d, time.min)


def _date_end_excl(d: date) -> datetime:
    return datetime.combine(d + timedelta(days=1), time.min)


def entitlement_status_counts(
    db: Session, tenant_id: UUID, shop_id: UUID | None = None
) -> dict[str, int]:
    base = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.tenant_id, tenant_id))
    if shop_id:
        base = base.filter(uuid_eq(ShopEntitlement.shop_id, shop_id))
    counts = {"all": base.count()}
    for st in ("pending", "revoked", "expired"):
        counts[st] = base.filter(ShopEntitlement.status == st).count()
    counts["consumed"] = base.filter(
        ShopEntitlement.status == "active",
        ShopEntitlement.remaining_count == 0,
    ).count()
    counts["active"] = base.filter(
        ShopEntitlement.status == "active",
        _not_consumed(),
    ).count()
    return counts


def list_entitlements_merchant(
    db: Session,
    ctx: TenantContext,
    *,
    status_filter: str | None,
    page: int,
    page_size: int,
    q: str | None = None,
    product_type: str | None = None,
    buyer_id: UUID | None = None,
    shop_id: UUID | None = None,
    activated_from: date | None = None,
    activated_to: date | None = None,
    expires_from: date | None = None,
    expires_to: date | None = None,
) -> tuple[list[EntitlementOut], int, dict[str, int]]:
    query = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.tenant_id, ctx.tenant_id))
    if shop_id:
        query = query.filter(uuid_eq(ShopEntitlement.shop_id, shop_id))
    if buyer_id:
        query = query.filter(uuid_eq(ShopEntitlement.buyer_id, buyer_id))
    if status_filter == "consumed":
        query = query.filter(
            ShopEntitlement.status == "active",
            ShopEntitlement.remaining_count == 0,
        )
    elif status_filter == "active":
        query = query.filter(ShopEntitlement.status == "active", _not_consumed())
    elif status_filter:
        query = query.filter(ShopEntitlement.status == status_filter)
    if activated_from is not None:
        query = query.filter(ShopEntitlement.activated_at >= _date_start(activated_from))
    if activated_to is not None:
        query = query.filter(ShopEntitlement.activated_at < _date_end_excl(activated_to))
    if expires_from is not None:
        query = query.filter(ShopEntitlement.expires_at >= _date_start(expires_from))
    if expires_to is not None:
        query = query.filter(ShopEntitlement.expires_at < _date_end_excl(expires_to))
    if product_type:
        pids = [
            p.id
            for p in db.query(ShopProduct.id)
            .filter(
                uuid_eq(ShopProduct.tenant_id, ctx.tenant_id),
                ShopProduct.type == product_type,
            )
            .all()
        ]
        query = query.filter(ShopEntitlement.product_id.in_(pids or [uuid.UUID(int=0)]))
    if q:
        qq = q.strip()
        buyers = (
            db.query(ShopBuyer.id)
            .filter(
                uuid_eq(ShopBuyer.tenant_id, ctx.tenant_id),
                ShopBuyer.mobile.contains(qq),
            )
            .all()
        )
        orders = (
            db.query(ShopOrder.id)
            .filter(
                uuid_eq(ShopOrder.tenant_id, ctx.tenant_id),
                ShopOrder.order_no.contains(qq),
            )
            .all()
        )
        query = query.filter(
            or_(
                ShopEntitlement.buyer_id.in_([b.id for b in buyers] or [uuid.UUID(int=0)]),
                ShopEntitlement.order_id.in_([o.id for o in orders] or [uuid.UUID(int=0)]),
            )
        )
    total = query.count()
    rows = (
        query.order_by(ShopEntitlement.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    pids = {e.product_id for e in rows}
    products = {
        p.id: p
        for p in db.query(ShopProduct).filter(ShopProduct.id.in_(list(pids))).all()
    } if pids else {}
    buyers = _buyers_map(db, {e.buyer_id for e in rows})
    orders = {
        o.id: o
        for o in db.query(ShopOrder).filter(ShopOrder.id.in_([e.order_id for e in rows])).all()
    } if rows else {}
    shops = {
        s.id: s
        for s in db.query(ShopStore).filter(ShopStore.id.in_({e.shop_id for e in rows})).all()
    } if rows else {}
    items = [
        _entitlement_out(
            e,
            products.get(e.product_id),
            buyer=buyers.get(e.buyer_id),
            order=orders.get(e.order_id),
            shop=shops.get(e.shop_id),
        )
        for e in rows
    ]
    return items, total, entitlement_status_counts(db, ctx.tenant_id, shop_id=shop_id)


def export_entitlements_csv(
    db: Session,
    ctx: TenantContext,
    *,
    status_filter: str | None = None,
    q: str | None = None,
    product_type: str | None = None,
    buyer_id: UUID | None = None,
    shop_id: UUID | None = None,
    activated_from: date | None = None,
    activated_to: date | None = None,
    expires_from: date | None = None,
    expires_to: date | None = None,
) -> str:
    items, total, _ = list_entitlements_merchant(
        db,
        ctx,
        status_filter=status_filter,
        page=1,
        page_size=5000,
        q=q,
        product_type=product_type,
        buyer_id=buyer_id,
        shop_id=shop_id,
        activated_from=activated_from,
        activated_to=activated_to,
        expires_from=expires_from,
        expires_to=expires_to,
    )
    if total > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    status_label = {
        "pending": "待生效",
        "active": "生效中",
        "revoked": "已撤销",
        "expired": "已过期",
        "consumed": "已用尽",
    }
    type_label = {"course": "课程", "digital": "资料", "service": "服务"}
    lines = ["买家,商品,类型,状态,次数,订单,开通时间,到期时间"]
    for r in items:
        st = (
            "已用尽"
            if r.status == "active" and r.remaining_count == 0
            else status_label.get(r.status, r.status or "")
        )
        times = (
            f"{r.remaining_count}/{r.total_count}"
            if r.remaining_count is not None
            else ""
        )
        lines.append(
            ",".join(
                [
                    (r.buyer_mobile_masked or "").replace(",", " "),
                    (r.product_name or "").replace(",", " "),
                    type_label.get(r.product_type or "", r.product_type or ""),
                    st,
                    times,
                    r.order_no or "",
                    str(r.activated_at or ""),
                    str(r.expires_at or ""),
                ]
            )
        )
    return "\n".join(lines)


def create_entitlement_export_task(
    db: Session, ctx: TenantContext, body: EntitlementExportRequest | None = None
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    body = body or EntitlementExportRequest()
    filters = {
        "status": body.status,
        "q": body.q,
        "product_type": body.product_type,
        "shop_id": str(body.shop_id) if body.shop_id else None,
        "activated_from": str(body.activated_from) if body.activated_from else None,
        "activated_to": str(body.activated_to) if body.activated_to else None,
        "expires_from": str(body.expires_from) if body.expires_from else None,
        "expires_to": str(body.expires_to) if body.expires_to else None,
    }
    csv_text = export_entitlements_csv(
        db,
        ctx,
        status_filter=body.status,
        q=body.q,
        product_type=body.product_type,
        shop_id=body.shop_id,
        activated_from=body.activated_from,
        activated_to=body.activated_to,
        expires_from=body.expires_from,
        expires_to=body.expires_to,
    )
    return export_task_service.persist_csv_task(
        db,
        ctx,
        resource="entitlements",
        file_name="shop-entitlements.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_entitlement_export_task(
    db: Session, ctx: TenantContext, task_id: UUID
) -> ShopExportTaskOut:
    from app.services.shop import export_task_service

    return export_task_service.get_task(db, ctx, task_id, "entitlements")


def read_entitlement_export_file(db: Session, ctx: TenantContext, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file(db, ctx, task_id, "entitlements")


def get_entitlement_merchant(
    db: Session, ctx: TenantContext, entitlement_id: UUID
) -> EntitlementOut:
    e = (
        db.query(ShopEntitlement)
        .filter(
            uuid_eq(ShopEntitlement.id, entitlement_id),
            uuid_eq(ShopEntitlement.tenant_id, ctx.tenant_id),
        )
        .first()
    )
    if not e:
        raise HTTPException(status_code=404, detail="权益不存在")
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, e.product_id)).first()
    buyer = db.query(ShopBuyer).filter(uuid_eq(ShopBuyer.id, e.buyer_id)).first()
    order = db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, e.order_id)).first()
    shop = db.query(ShopStore).filter(uuid_eq(ShopStore.id, e.shop_id)).first()
    mode = None
    if product and product.ref_type == "service_offer" and product.ref_id:
        from app.models.shop import ShopServiceOffer

        offer = (
            db.query(ShopServiceOffer)
            .filter(uuid_eq(ShopServiceOffer.id, product.ref_id))
            .first()
        )
        mode = offer.mode if offer else None
    return _entitlement_out(
        e, product, service_mode=mode, buyer=buyer, order=order, shop=shop
    )


def list_entitlements_buyer(
    db: Session, buyer: ShopBuyer, *, page: int, page_size: int
) -> tuple[list[EntitlementOut], int]:
    query = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.buyer_id, buyer.id))
    total = query.count()
    rows = (
        query.order_by(ShopEntitlement.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    pids = {e.product_id for e in rows}
    products = {
        p.id: p
        for p in db.query(ShopProduct).filter(ShopProduct.id.in_(list(pids))).all()
    } if pids else {}
    from app.models.shop import ShopServiceOffer

    offer_ids = {
        p.ref_id
        for p in products.values()
        if p.ref_type == "service_offer" and p.ref_id
    }
    modes = {
        o.id: o.mode
        for o in db.query(ShopServiceOffer).filter(ShopServiceOffer.id.in_(list(offer_ids))).all()
    } if offer_ids else {}
    out = []
    for e in rows:
        p = products.get(e.product_id)
        mode = modes.get(p.ref_id) if p and p.ref_type == "service_offer" and p.ref_id else None
        out.append(_entitlement_out(e, p, service_mode=mode))
    return out, total


def assert_entitlement_active(db: Session, entitlement_id: UUID, buyer_id: UUID | None = None) -> EntitlementOut:
    """履约闸：revoked/expired → 403。"""
    e = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.id, entitlement_id)).first()
    if not e:
        raise HTTPException(status_code=404, detail="权益不存在")
    if buyer_id and e.buyer_id != buyer_id:
        raise HTTPException(status_code=404, detail="权益不存在")
    if e.status == "revoked":
        raise HTTPException(status_code=403, detail="权益已撤销")
    if e.status == "expired":
        raise HTTPException(status_code=403, detail="权益已过期")
    if e.status != "active":
        raise HTTPException(status_code=422, detail=f"权益状态为 {e.status}，不可履约")
    product = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, e.product_id)).first()
    return _entitlement_out(e, product)


def replay_refund_success(db: Session, refund_id: UUID) -> RefundOut:
    """模拟退款回调重复：状态保持 succeeded，不重复副作用。"""
    r = db.query(ShopRefund).filter(uuid_eq(ShopRefund.id, refund_id)).first()
    if not r:
        raise HTTPException(status_code=404, detail="退款单不存在")
    order = db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, r.order_id)).first()
    if r.status == "succeeded":
        return _refund_out(r, order)
    if order:
        _complete_refund_success(db, order, r)
        db.commit()
        db.refresh(r)
        db.refresh(order)
    return _refund_out(r, order)
