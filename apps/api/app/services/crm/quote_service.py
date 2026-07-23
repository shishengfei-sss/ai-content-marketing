"""报价服务（v0.7 CRM-2）。

CRUD + 报价行 + 状态机（draft/sent/accepted/rejected/expired/ordered）+ 转订单。
状态推进仅走专用动作；PATCH 禁止改 status，非 draft 禁止改明细。
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
from app.services.crm.crm_scope_service import assert_can_mutate_quote, assert_can_view_quote, _perm_set
from app.services.crm.number_service import generate_number
from app.services.crm.schema_service import validate_extra_data
from app.services.crm.tax_engine import TaxLineIn, compute_tax_lines

# draft 可改的业务字段（不含 status）
_PATCH_MUTATE_FIELDS = frozenset(
    {
        "deal_id",
        "customer_id",
        "contact_id",
        "subject",
        "discount_rate",
        "total_amount",
        "valid_until",
        "extra_data",
        "lines",
        "cpq_config_snapshot",
    }
)


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


def _normalize_dt(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_past_valid_until(quote: Quote) -> bool:
    vu = _normalize_dt(quote.valid_until)
    if vu is None:
        return False
    return vu < datetime.now(timezone.utc)


def _replace_lines(
    db: Session,
    quote: Quote,
    lines: list[QuoteLineCreate],
    *,
    header_discount_rate: float | None = None,
) -> None:
    """写入明细：价税引擎（含头折摊入 + 税额尾差）。"""
    db.query(QuoteLine).filter(QuoteLine.quote_id == quote.id).delete(synchronize_session=False)
    hdr = header_discount_rate if header_discount_rate is not None else quote.discount_rate
    engine_in = [
        TaxLineIn(
            unit_price=ln.unit_price,
            quantity=ln.quantity,
            discount_rate=ln.discount_rate,
            tax_rate=ln.tax_rate,
        )
        for ln in lines
    ]
    result = compute_tax_lines(engine_in, header_discount_rate=hdr)
    for i, (ln, out) in enumerate(zip(lines, result.lines)):
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
                tax_rate=float(out.tax_rate) if out.tax_rate is not None else ln.tax_rate,
                tax_amount=float(out.tax_amount),
                line_total=float(out.line_total),
                sort_order=ln.sort_order if ln.sort_order is not None else i,
                remark=ln.remark,
            )
        )
    quote.total_amount = float(result.total_ex_tax)
    db.flush()


def _recompute_total(db: Session, quote: Quote) -> None:
    """已存行的 line_total 已是头折后未税，直接求和。"""
    lines = _load_lines(db, quote.id)
    quote.total_amount = round(sum(float(l.line_total or 0) for l in lines), 2)


def create_quote(db: Session, ctx: TenantContext, data: QuoteCreate) -> Quote:
    extra = validate_extra_data(db, ctx.tenant_id, "quote", data.extra_data, is_create=True)
    owner_user_id = ctx.user.id
    if data.owner_user_id is not None and data.owner_user_id != ctx.user.id:
        if "crm.quote.edit" not in _perm_set(ctx):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        owner_user_id = data.owner_user_id
    quote_number = data.quote_number or _generate_quote_number(db, ctx.tenant_id)
    # 新建一律 draft（忽略客户端传入的非 draft）
    quote = Quote(
        tenant_id=ctx.tenant_id,
        quote_number=quote_number,
        deal_id=data.deal_id,
        customer_id=data.customer_id,
        contact_id=data.contact_id,
        subject=data.subject.strip(),
        discount_rate=data.discount_rate,
        total_amount=data.total_amount,
        status="draft",
        valid_until=data.valid_until,
        owner_user_id=owner_user_id,
        extra_data=extra,
        cpq_config_snapshot=data.cpq_config_snapshot,
        created_by_user_id=ctx.user.id,
    )
    db.add(quote)
    db.flush()
    if data.lines:
        _replace_lines(db, quote, data.lines, header_discount_rate=data.discount_rate)
    db.commit()
    db.refresh(quote)
    return quote


def update_quote(db: Session, ctx: TenantContext, quote: Quote, data: QuoteUpdate) -> Quote:
    perms = _perm_set(ctx)
    set_keys = set(data.model_fields_set)

    if "status" in set_keys:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="禁止通过 PATCH 修改 status，请使用 send/accept/reject/recall/convert 等专用接口",
        )

    mutate_keys = set_keys - {"owner_user_id"}
    if mutate_keys:
        assert_can_mutate_quote(ctx, quote)
        if quote.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"报价已 {quote.status}，仅草稿可修改内容；请复制或撤回后再改",
            )
        unknown = mutate_keys - _PATCH_MUTATE_FIELDS
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"不允许修改字段: {sorted(unknown)}",
            )
    elif "owner_user_id" in set_keys:
        # 仅改负责人：draft/sent/accepted/rejected 允许；expired/ordered 禁止
        if quote.status in ("expired", "ordered"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"报价已 {quote.status}，不可再分配负责人",
            )
    else:
        return quote

    if data.owner_user_id is not None and data.owner_user_id != quote.owner_user_id:
        if "crm.quote.edit" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        quote.owner_user_id = data.owner_user_id

    if quote.status == "draft":
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
        if data.valid_until is not None:
            quote.valid_until = data.valid_until
        if data.extra_data is not None:
            merged = dict(quote.extra_data or {})
            merged.update(data.extra_data)
            quote.extra_data = validate_extra_data(db, ctx.tenant_id, "quote", merged)
        if data.cpq_config_snapshot is not None:
            quote.cpq_config_snapshot = data.cpq_config_snapshot
        if data.lines is not None:
            _replace_lines(db, quote, data.lines, header_discount_rate=quote.discount_rate)
        elif data.discount_rate is not None:
            existing = _load_lines(db, quote.id)
            payloads = [
                QuoteLineCreate(
                    product_id=ln.product_id,
                    name=ln.name,
                    unit=ln.unit,
                    quantity=float(ln.quantity or 0),
                    unit_price=float(ln.unit_price or 0),
                    discount_rate=float(ln.discount_rate) if ln.discount_rate is not None else None,
                    tax_rate=float(ln.tax_rate) if ln.tax_rate is not None else None,
                    line_total=float(ln.line_total or 0),
                    sort_order=ln.sort_order or i,
                    remark=ln.remark,
                )
                for i, ln in enumerate(existing)
            ]
            if payloads:
                _replace_lines(db, quote, payloads, header_discount_rate=quote.discount_rate)
            else:
                _recompute_total(db, quote)
        elif mutate_keys:
            _recompute_total(db, quote)

    db.commit()
    db.refresh(quote)
    return quote


def send_quote(db: Session, ctx: TenantContext, quote: Quote) -> Quote:
    assert_can_mutate_quote(ctx, quote)
    if quote.status == "sent":
        return quote  # 幂等
    if quote.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"报价已 {quote.status}，不可发送")
    lines = _load_lines(db, quote.id)
    if not lines:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="报价无明细，不可发送")
    quote.status = "sent"
    db.commit()
    db.refresh(quote)
    return quote


def accept_quote(db: Session, ctx: TenantContext, quote: Quote) -> Quote:
    assert_can_mutate_quote(ctx, quote)
    if quote.status == "accepted":
        return quote  # 幂等
    if quote.status != "sent":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"报价已 {quote.status}，不可标记接受")
    if _is_past_valid_until(quote):
        quote.status = "expired"
        db.commit()
        db.refresh(quote)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="报价已过期，不可接受")
    quote.status = "accepted"
    db.commit()
    db.refresh(quote)
    return quote


def reject_quote(db: Session, ctx: TenantContext, quote: Quote, reason: str | None = None) -> Quote:
    assert_can_mutate_quote(ctx, quote)
    if quote.status == "rejected":
        return quote  # 幂等
    if quote.status != "sent":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"报价已 {quote.status}，不可拒绝")
    quote.status = "rejected"
    if reason:
        extra = dict(quote.extra_data or {})
        extra["reject_reason"] = reason.strip()[:500]
        quote.extra_data = extra
    db.commit()
    db.refresh(quote)
    return quote


def recall_quote(db: Session, ctx: TenantContext, quote: Quote) -> Quote:
    """撤回已发送报价为草稿，便于改价（P1）。"""
    assert_can_mutate_quote(ctx, quote)
    if quote.status != "sent":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"报价已 {quote.status}，不可撤回")
    quote.status = "draft"
    db.commit()
    db.refresh(quote)
    return quote


def soft_delete_quote(db: Session, ctx: TenantContext, quote: Quote) -> None:
    assert_can_mutate_quote(ctx, quote)
    # 已发送请先撤回/拒绝；与撤回、拒绝操作互斥
    if quote.status not in ("draft", "rejected", "expired"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"报价状态为 {quote.status}，不可删除（已发送请先撤回或拒绝）",
        )
    quote.deleted_at = datetime.now(timezone.utc)
    db.query(QuoteLine).filter(QuoteLine.quote_id == quote.id).delete(synchronize_session=False)
    db.commit()


def clone_quote(db: Session, ctx: TenantContext, quote: Quote) -> Quote:
    """复制报价为新草稿（FR-CPQ-09）。保留明细与 CPQ 快照。"""
    lines = _load_lines(db, quote.id)
    line_payloads = [
        QuoteLineCreate(
            product_id=ln.product_id,
            name=ln.name,
            unit=ln.unit,
            quantity=float(ln.quantity or 0),
            unit_price=float(ln.unit_price or 0),
            discount_rate=float(ln.discount_rate) if ln.discount_rate is not None else None,
            tax_rate=float(ln.tax_rate) if ln.tax_rate is not None else None,
            tax_amount=float(ln.tax_amount) if ln.tax_amount is not None else None,
            line_total=float(ln.line_total or 0),
            sort_order=ln.sort_order or i,
            remark=ln.remark,
        )
        for i, ln in enumerate(lines)
    ]
    snap = dict(quote.cpq_config_snapshot) if quote.cpq_config_snapshot else None
    return create_quote(
        db,
        ctx,
        QuoteCreate(
            customer_id=quote.customer_id,
            deal_id=quote.deal_id,
            contact_id=quote.contact_id,
            subject=f"{quote.subject}（复制）",
            discount_rate=float(quote.discount_rate) if quote.discount_rate is not None else None,
            total_amount=float(quote.total_amount or 0),
            status="draft",
            valid_until=quote.valid_until,
            lines=line_payloads,
            cpq_config_snapshot=snap,
            extra_data={"source": "clone", "cloned_from": str(quote.id)},
        ),
    )


def convert_quote_to_order(db: Session, ctx: TenantContext, quote: Quote) -> Order:
    """报价转订单（source=quote）。仅 accepted；明细含税；头折已摊入时折算有效单价。"""
    assert_can_mutate_quote(ctx, quote)
    if quote.status != "accepted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"报价已 {quote.status}，仅已接受的报价可转订单",
        )
    if quote.converted_order_id:
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
    quote_lines = _load_lines(db, quote.id)
    from app.models.crm import OrderLine

    header_applied = bool(quote.discount_rate and float(quote.discount_rate) > 0)
    for i, ln in enumerate(quote_lines):
        qty = float(ln.quantity or 0) or 1.0
        unit_price = float(ln.unit_price or 0)
        disc = float(ln.discount_rate) if ln.discount_rate is not None else None
        if header_applied:
            unit_price = round(float(ln.line_total or 0) / qty, 2)
            disc = None
        db.add(
            OrderLine(
                tenant_id=ctx.tenant_id,
                order_id=order.id,
                product_id=ln.product_id,
                name=ln.name,
                unit=ln.unit,
                quantity=ln.quantity,
                unit_price=unit_price,
                discount_rate=disc,
                tax_rate=ln.tax_rate,
                tax_amount=ln.tax_amount,
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
