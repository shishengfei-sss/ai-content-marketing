"""报价服务（v0.7 CRM-2）。

CRUD + 报价行 + 状态推进（草稿/发送/接受） + 转订单。
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Order, Quote, QuoteLine
from app.schemas.crm_deals import QuoteCreate, QuoteLineCreate, QuoteUpdate
from app.services.crm.crm_scope_service import assert_can_view_quote, _perm_set
from app.services.crm.number_service import generate_number
from app.services.crm.schema_service import validate_extra_data


def get_quote(db: Session, tenant_id: UUID, quote_id: UUID) -> Quote | None:
    return (
        db.query(Quote)
        .filter(uuid_eq(Quote.id, quote_id), Quote.tenant_id == tenant_id, Quote.deleted_at.is_(None))
        .first()
    )


def require_quote(db: Session, ctx: TenantContext, quote_id: UUID) -> Quote:
    q = get_quote(db, ctx.tenant_id, quote_id)
    if not q:
        raise HTTPException(status_code=404, detail="报价不存在")
    assert_can_view_quote(ctx, db, q.owner_user_id)
    return q


def _load_lines(db: Session, quote_id: UUID) -> list[QuoteLine]:
    return (
        db.query(QuoteLine)
        .filter(QuoteLine.quote_id == quote_id)
        .order_by(QuoteLine.sort_order, QuoteLine.id)
        .all()
    )


def _generate_quote_number(db: Session, tenant_id: UUID) -> str:
    return generate_number(db, tenant_id, "quote")


def _generate_order_number(db: Session, tenant_id: UUID) -> str:
    return generate_number(db, tenant_id, "order")


def _replace_lines(db: Session, quote: Quote, lines: list[QuoteLineCreate]) -> None:
    # 删除旧明细
    db.query(QuoteLine).filter(QuoteLine.quote_id == quote.id).delete(synchronize_session=False)
    for i, ln in enumerate(lines):
        line_total = ln.line_total if ln.line_total else float(ln.quantity) * float(ln.unit_price) * (
            1 - (float(ln.discount_rate or 0) / 100)
        )
        db.add(
            QuoteLine(
                tenant_id=quote.tenant_id,
                quote_id=quote.id,
                product_id=ln.product_id,
                name=ln.name,
                unit=ln.unit,
                quantity=ln.quantity,
                unit_price=ln.unit_price,
                discount_rate=ln.discount_rate,
                line_total=line_total,
                sort_order=ln.sort_order if ln.sort_order is not None else i,
                remark=ln.remark,
            )
        )
    db.flush()  # 确保新明细落库，供后续 _load_lines 查询


def _recompute_total(db: Session, quote: Quote) -> None:
    lines = _load_lines(db, quote.id)
    total = sum(float(l.line_total) for l in lines)
    if quote.discount_rate:
        total = total * (1 - float(quote.discount_rate) / 100)
    quote.total_amount = round(total, 2)


def create_quote(db: Session, ctx: TenantContext, data: QuoteCreate) -> Quote:
    extra = validate_extra_data(db, ctx.tenant_id, "quote", data.extra_data, is_create=True)
    owner_user_id = ctx.user.id
    if data.owner_user_id is not None and data.owner_user_id != ctx.user.id:
        if "crm.quote.edit" not in _perm_set(ctx):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        owner_user_id = data.owner_user_id
    quote_number = data.quote_number or _generate_quote_number(db, ctx.tenant_id)
    quote = Quote(
        tenant_id=ctx.tenant_id,
        quote_number=quote_number,
        deal_id=data.deal_id,
        customer_id=data.customer_id,
        contact_id=data.contact_id,
        subject=data.subject.strip(),
        discount_rate=data.discount_rate,
        total_amount=data.total_amount,
        status=data.status,
        valid_until=data.valid_until,
        owner_user_id=owner_user_id,
        extra_data=extra,
        created_by_user_id=ctx.user.id,
    )
    db.add(quote)
    db.flush()
    if data.lines:
        _replace_lines(db, quote, data.lines)
        _recompute_total(db, quote)
    db.commit()
    db.refresh(quote)
    return quote


def update_quote(db: Session, ctx: TenantContext, quote: Quote, data: QuoteUpdate) -> Quote:
    perms = _perm_set(ctx)
    if data.owner_user_id is not None and data.owner_user_id != quote.owner_user_id:
        if "crm.quote.edit" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        quote.owner_user_id = data.owner_user_id
    if data.deal_id is not None:
        quote.deal_id = data.deal_id
    if data.customer_id is not None:
        quote.customer_id = data.customer_id
    if data.contact_id is not None:
        quote.contact_id = data.contact_id
    if data.subject is not None:
        quote.subject = data.subject.strip()
    if data.discount_rate is not None:
        quote.discount_rate = data.discount_rate
    if data.status is not None:
        quote.status = data.status
    if data.valid_until is not None:
        quote.valid_until = data.valid_until
    if data.extra_data is not None:
        merged = dict(quote.extra_data or {})
        merged.update(data.extra_data)
        quote.extra_data = validate_extra_data(db, ctx.tenant_id, "quote", merged)
    if data.lines is not None:
        _replace_lines(db, quote, data.lines)
    _recompute_total(db, quote)
    db.commit()
    db.refresh(quote)
    return quote


def send_quote(db: Session, ctx: TenantContext, quote: Quote) -> Quote:
    if quote.status not in ("draft", "sent"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"报价已 {quote.status}，不可发送")
    quote.status = "sent"
    db.commit()
    db.refresh(quote)
    return quote


def accept_quote(db: Session, ctx: TenantContext, quote: Quote) -> Quote:
    if quote.status not in ("sent", "accepted"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"报价已 {quote.status}，不可标记接受")
    quote.status = "accepted"
    db.commit()
    db.refresh(quote)
    return quote


def soft_delete_quote(db: Session, quote: Quote) -> None:
    quote.deleted_at = datetime.now(timezone.utc)
    db.query(QuoteLine).filter(QuoteLine.quote_id == quote.id).delete(synchronize_session=False)
    db.commit()


def convert_quote_to_order(db: Session, ctx: TenantContext, quote: Quote) -> Order:
    """报价转订单（source=quote）。

    BR-ORDER-01：customer_id 必填（来自报价）。
    明细一并复制到订单行。
    """
    if quote.status not in ("accepted", "draft", "sent"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"报价已 {quote.status}，不可转订单")
    if quote.converted_order_id:
        # 允许多次转单？为简化，仅允许一次。如需多次可去掉该校验。
        existing = db.query(Order).filter(Order.id == quote.converted_order_id, Order.deleted_at.is_(None)).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该报价已转订单")
    order = Order(
        tenant_id=ctx.tenant_id,
        order_number=_generate_order_number(db, ctx.tenant_id),
        title=f"由报价「{quote.subject}」生成",
        customer_id=quote.customer_id,
        contact_id=quote.contact_id,
        deal_id=quote.deal_id,
        quote_id=quote.id,
        contract_id=None,
        source="quote",
        order_date=datetime.now(timezone.utc),
        amount=float(quote.total_amount),
        status="draft",
        owner_user_id=quote.owner_user_id,
        territory_id=None,
        extra_data={},
        created_by_user_id=ctx.user.id,
    )
    db.add(order)
    db.flush()
    # 复制明细为订单行
    quote_lines = _load_lines(db, quote.id)
    from app.models.crm import OrderLine

    for i, ln in enumerate(quote_lines):
        db.add(
            OrderLine(
                tenant_id=ctx.tenant_id,
                order_id=order.id,
                product_id=ln.product_id,
                name=ln.name,
                unit=ln.unit,
                quantity=ln.quantity,
                unit_price=ln.unit_price,
                discount_rate=ln.discount_rate,
                line_total=ln.line_total,
                sort_order=ln.sort_order if ln.sort_order is not None else i,
                remark=ln.remark,
            )
        )
    quote.converted_order_id = order.id
    quote.status = "ordered"
    db.commit()
    db.refresh(order)
    return order
