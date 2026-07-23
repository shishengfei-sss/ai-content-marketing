"""CPQ 轻量服务：价目取价 + 参数价差 + calculate（v1.3 W1–2）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import ParamPricing, PriceBook, PriceBookEntry, Product, ProductParam, ProductVariant
from app.schemas.crm_cpq import (
    CpqCalculateOut,
    CpqCalculateRequest,
    CpqSaveQuoteRequest,
    ParamPricingCreate,
    ParamPricingUpdate,
    ProductParamCreate,
    ProductParamUpdate,
    ResolvePriceOut,
    ResolvePriceRequest,
)
from app.schemas.crm_deals import QuoteCreate, QuoteLineCreate, QuoteLineOut, QuoteOut
from app.services.crm.product_service import require_product
from app.services.crm.quote_service import _load_lines, create_quote


def _now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_unit_price(db: Session, ctx: TenantContext, req: ResolvePriceRequest) -> ResolvePriceOut:
    product = require_product(db, ctx, req.product_id)
    variant: ProductVariant | None = None
    if req.variant_id:
        variant = (
            db.query(ProductVariant)
            .filter(
                ProductVariant.id == req.variant_id,
                ProductVariant.tenant_id == ctx.tenant_id,
                ProductVariant.product_id == product.id,
            )
            .first()
        )
        if not variant:
            raise HTTPException(status_code=400, detail="变体与产品不匹配")

    book: PriceBook | None = None
    if req.price_book_id:
        book = (
            db.query(PriceBook)
            .filter(
                PriceBook.id == req.price_book_id,
                PriceBook.tenant_id == ctx.tenant_id,
                PriceBook.is_active.is_(True),
            )
            .first()
        )
        if not book:
            raise HTTPException(status_code=404, detail="价目表不存在或未启用")
    else:
        book = (
            db.query(PriceBook)
            .filter(
                PriceBook.tenant_id == ctx.tenant_id,
                PriceBook.is_active.is_(True),
                PriceBook.is_default.is_(True),
            )
            .first()
        )

    qty = int(req.quantity) if req.quantity == int(req.quantity) else int(req.quantity) + 1
    qty = max(qty, 1)
    now = _now()

    if book:
        entries = (
            db.query(PriceBookEntry)
            .filter(
                PriceBookEntry.tenant_id == ctx.tenant_id,
                PriceBookEntry.price_book_id == book.id,
                PriceBookEntry.product_id == product.id,
                PriceBookEntry.min_quantity <= qty,
            )
            .order_by(PriceBookEntry.min_quantity.desc())
            .all()
        )
        for entry in entries:
            if req.variant_id and entry.variant_id and entry.variant_id != req.variant_id:
                continue
            if req.variant_id is None and entry.variant_id is not None:
                continue
            if entry.valid_from and entry.valid_from > now:
                continue
            if entry.valid_to and entry.valid_to < now:
                continue
            levels = entry.customer_levels or []
            if levels and req.customer_level and req.customer_level not in levels:
                continue
            if levels and not req.customer_level:
                continue
            return ResolvePriceOut(
                product_id=product.id,
                variant_id=req.variant_id,
                unit_price=float(entry.unit_price),
                source="price_book",
                price_book_id=book.id,
                price_book_entry_id=entry.id,
                min_quantity=entry.min_quantity,
            )

    if variant is not None:
        return ResolvePriceOut(
            product_id=product.id,
            variant_id=variant.id,
            unit_price=float(variant.list_price or 0),
            source="variant_list_price",
            price_book_id=book.id if book else None,
        )

    return ResolvePriceOut(
        product_id=product.id,
        variant_id=None,
        unit_price=float(product.list_price or 0),
        source="product_list_price",
        price_book_id=book.id if book else None,
    )


def _apply_adjustment(base: float, adj_type: str, adj_value: float) -> float:
    if adj_type == "fixed":
        return base + adj_value
    if adj_type == "percentage":
        return base * (1 + adj_value / 100.0)
    if adj_type == "multiplier":
        return base * adj_value
    raise HTTPException(status_code=400, detail=f"未知价差类型: {adj_type}")


def calculate_quote(db: Session, ctx: TenantContext, req: CpqCalculateRequest) -> CpqCalculateOut:
    product = require_product(db, ctx, req.product_id)
    resolved = resolve_unit_price(
        db,
        ctx,
        ResolvePriceRequest(
            product_id=req.product_id,
            variant_id=req.variant_id,
            quantity=req.quantity,
            customer_level=req.customer_level,
            price_book_id=req.price_book_id,
        ),
    )
    unit = resolved.unit_price
    adjustments: list[dict[str, Any]] = []

    if req.selected_params:
        params = list_params(db, ctx, product.id, include_inactive=False)
        by_name = {p.param_name: p for p in params}
        for name, value in req.selected_params.items():
            param = by_name.get(name)
            if not param:
                continue
            val_str = str(value)
            pricing = next((x for x in getattr(param, "pricings", []) if x.option_value == val_str), None)
            if not pricing:
                continue
            before = unit
            unit = _apply_adjustment(unit, pricing.price_adjustment_type, float(pricing.price_adjustment_value))
            adjustments.append(
                {
                    "param_name": name,
                    "option_value": val_str,
                    "type": pricing.price_adjustment_type,
                    "value": float(pricing.price_adjustment_value),
                    "delta": round(unit - before, 4),
                }
            )

    subtotal = unit * float(req.quantity)
    discount_amount = subtotal * (float(req.discount_rate) / 100.0)
    final_price = subtotal - discount_amount + float(req.shipping_cost)
    cost = float(product.cost_price) if product.cost_price is not None else None
    margin_pct = None
    margin_warning = False
    if cost is not None and final_price > 0:
        total_cost = cost * float(req.quantity)
        margin_pct = round((final_price - total_cost) / final_price * 100.0, 2)
        if req.min_margin_pct is not None and margin_pct < req.min_margin_pct:
            margin_warning = True
            if not req.confirm_low_margin:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "LOW_MARGIN",
                        "message": f"毛利率 {margin_pct}% 低于红线 {req.min_margin_pct}%",
                        "profit_margin_pct": margin_pct,
                    },
                )

    return CpqCalculateOut(
        product_id=product.id,
        base_unit_price=resolved.unit_price,
        adjusted_unit_price=round(unit, 4),
        quantity=float(req.quantity),
        subtotal=round(subtotal, 2),
        discount_rate=float(req.discount_rate),
        discount_amount=round(discount_amount, 2),
        shipping_cost=float(req.shipping_cost),
        final_price=round(final_price, 2),
        cost_estimate=round(cost * float(req.quantity), 2) if cost is not None else None,
        profit_margin_pct=margin_pct,
        margin_warning=margin_warning,
        price_source=resolved.source,
        price_book_id=resolved.price_book_id,
        param_adjustments=adjustments,
    )


# ---- params CRUD ----

def list_params(
    db: Session, ctx: TenantContext, product_id: UUID, *, include_inactive: bool = True
) -> list[ProductParam]:
    require_product(db, ctx, product_id)
    q = (
        db.query(ProductParam)
        .filter(ProductParam.tenant_id == ctx.tenant_id, ProductParam.product_id == product_id)
        .order_by(ProductParam.sort_order.asc(), ProductParam.created_at.asc())
    )
    if not include_inactive:
        q = q.filter(ProductParam.is_active.is_(True))
    params = q.all()
    # attach pricings
    if params:
        ids = [p.id for p in params]
        pricings = db.query(ParamPricing).filter(ParamPricing.param_id.in_(ids)).all()
        by_param: dict[UUID, list[ParamPricing]] = {}
        for pr in pricings:
            by_param.setdefault(pr.param_id, []).append(pr)
        for p in params:
            p.pricings = by_param.get(p.id, [])  # type: ignore[attr-defined]
    return params


def create_param(db: Session, ctx: TenantContext, product_id: UUID, data: ProductParamCreate) -> ProductParam:
    require_product(db, ctx, product_id)
    row = ProductParam(
        tenant_id=ctx.tenant_id,
        product_id=product_id,
        param_name=data.param_name.strip(),
        param_type=data.param_type,
        options=data.options,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    row.pricings = []  # type: ignore[attr-defined]
    return row


def get_param(db: Session, ctx: TenantContext, param_id: UUID) -> ProductParam:
    row = (
        db.query(ProductParam)
        .filter(ProductParam.id == param_id, ProductParam.tenant_id == ctx.tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="参数不存在")
    row.pricings = (  # type: ignore[attr-defined]
        db.query(ParamPricing).filter(ParamPricing.param_id == row.id).all()
    )
    return row


def update_param(db: Session, ctx: TenantContext, param: ProductParam, data: ProductParamUpdate) -> ProductParam:
    if data.param_name is not None:
        param.param_name = data.param_name.strip()
    if data.param_type is not None:
        param.param_type = data.param_type
    if data.options is not None:
        param.options = data.options
    if data.sort_order is not None:
        param.sort_order = data.sort_order
    if data.is_active is not None:
        param.is_active = data.is_active
    db.commit()
    db.refresh(param)
    return get_param(db, ctx, param.id)


def delete_param(db: Session, param: ProductParam) -> None:
    db.delete(param)
    db.commit()


def create_pricing(db: Session, ctx: TenantContext, param_id: UUID, data: ParamPricingCreate) -> ParamPricing:
    get_param(db, ctx, param_id)
    row = ParamPricing(
        param_id=param_id,
        option_value=data.option_value.strip(),
        price_adjustment_type=data.price_adjustment_type,
        price_adjustment_value=data.price_adjustment_value,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_pricing(db: Session, ctx: TenantContext, pricing_id: UUID, data: ParamPricingUpdate) -> ParamPricing:
    row = db.query(ParamPricing).filter(ParamPricing.id == pricing_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="价差映射不存在")
    get_param(db, ctx, row.param_id)
    if data.option_value is not None:
        row.option_value = data.option_value.strip()
    if data.price_adjustment_type is not None:
        row.price_adjustment_type = data.price_adjustment_type
    if data.price_adjustment_value is not None:
        row.price_adjustment_value = data.price_adjustment_value
    db.commit()
    db.refresh(row)
    return row


def delete_pricing(db: Session, ctx: TenantContext, pricing_id: UUID) -> None:
    row = db.query(ParamPricing).filter(ParamPricing.id == pricing_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="价差映射不存在")
    get_param(db, ctx, row.param_id)
    db.delete(row)
    db.commit()


def list_cpq_products(db: Session, ctx: TenantContext) -> list[Product]:
    return (
        db.query(Product)
        .filter(
            Product.tenant_id == ctx.tenant_id,
            Product.deleted_at.is_(None),
            Product.is_active.is_(True),
            Product.cpq_enabled.is_(True),
        )
        .order_by(Product.name.asc())
        .all()
    )


def save_cpq_as_quote(db: Session, ctx: TenantContext, req: CpqSaveQuoteRequest) -> QuoteOut:
    """服务端 calculate → 写入 quotes + quote_lines + cpq_config_snapshot。"""
    from app.models.crm import Customer, Deal, Lead
    from app.models.tender import ScoredTenderLead

    product = require_product(db, ctx, req.product_id)
    if not product.cpq_enabled:
        raise HTTPException(status_code=400, detail="产品未启用 CPQ")

    cust = (
        db.query(Customer)
        .filter(
            Customer.id == req.customer_id,
            Customer.tenant_id == ctx.tenant_id,
            Customer.deleted_at.is_(None),
        )
        .first()
    )
    if not cust:
        raise HTTPException(status_code=400, detail="须选择有效客户后方可报价（FR-CPQ-10）")

    if req.deal_id:
        deal = (
            db.query(Deal)
            .filter(Deal.id == req.deal_id, Deal.tenant_id == ctx.tenant_id, Deal.deleted_at.is_(None))
            .first()
        )
        if not deal:
            raise HTTPException(status_code=400, detail="关联商机不存在")
        if deal.customer_id != req.customer_id:
            raise HTTPException(status_code=400, detail="商机客户与报价客户不一致")

    if req.scored_tender_lead_id:
        scored = (
            db.query(ScoredTenderLead)
            .filter(
                ScoredTenderLead.id == req.scored_tender_lead_id,
                ScoredTenderLead.tenant_id == ctx.tenant_id,
            )
            .first()
        )
        if not scored:
            raise HTTPException(status_code=400, detail="关联招标线索不存在")
        if not scored.converted_lead_id:
            raise HTTPException(status_code=400, detail="须先纳入 CRM 线索后方可报价")
        lead = (
            db.query(Lead)
            .filter(Lead.id == scored.converted_lead_id, Lead.tenant_id == ctx.tenant_id)
            .first()
        )
        if not lead or not lead.converted_customer_id:
            raise HTTPException(status_code=400, detail="须将线索转化为客户后方可报价")
        if lead.converted_customer_id != req.customer_id:
            raise HTTPException(status_code=400, detail="招标线索关联客户与报价客户不一致")

    calc = calculate_quote(
        db,
        ctx,
        CpqCalculateRequest(
            product_id=req.product_id,
            variant_id=req.variant_id,
            quantity=req.quantity,
            customer_level=req.customer_level,
            price_book_id=req.price_book_id,
            selected_params=req.selected_params,
            discount_rate=req.discount_rate,
            shipping_cost=req.shipping_cost,
            min_margin_pct=req.min_margin_pct,
            confirm_low_margin=req.confirm_low_margin,
        ),
    )

    param_parts = [f"{k}={v}" for k, v in (req.selected_params or {}).items()]
    remark = ("配置: " + "; ".join(param_parts)) if param_parts else None
    lines: list[QuoteLineCreate] = [
        QuoteLineCreate(
            product_id=product.id,
            name=product.name,
            unit=product.unit,
            quantity=float(req.quantity),
            unit_price=float(calc.adjusted_unit_price),
            discount_rate=float(req.discount_rate) if req.discount_rate else None,
            line_total=round(float(calc.subtotal) - float(calc.discount_amount), 2),
            sort_order=0,
            remark=remark,
        )
    ]
    if float(req.shipping_cost) > 0:
        lines.append(
            QuoteLineCreate(
                product_id=None,
                name="运费",
                unit=None,
                quantity=1,
                unit_price=float(req.shipping_cost),
                discount_rate=None,
                line_total=float(req.shipping_cost),
                sort_order=1,
                remark="CPQ shipping",
            )
        )

    snapshot = {
        "version": 1,
        "product_id": str(product.id),
        "variant_id": str(req.variant_id) if req.variant_id else None,
        "selected_params": req.selected_params or {},
        "customer_level": req.customer_level,
        "price_book_id": str(req.price_book_id) if req.price_book_id else None,
        "quantity": float(req.quantity),
        "discount_rate": float(req.discount_rate),
        "shipping_cost": float(req.shipping_cost),
        "min_margin_pct": req.min_margin_pct,
        "confirm_low_margin": req.confirm_low_margin,
        "scored_tender_lead_id": str(req.scored_tender_lead_id) if req.scored_tender_lead_id else None,
        "deal_id": str(req.deal_id) if req.deal_id else None,
        "calculation": calc.model_dump(mode="json"),
    }

    quote = create_quote(
        db,
        ctx,
        QuoteCreate(
            customer_id=req.customer_id,
            deal_id=req.deal_id,
            contact_id=req.contact_id,
            subject=req.subject.strip(),
            discount_rate=None,  # 折扣已落在明细行，避免运费被二次折扣
            total_amount=float(calc.final_price),
            status="draft",
            valid_until=req.valid_until,
            lines=lines,
            cpq_config_snapshot=snapshot,
            extra_data={"source": "cpq"},
        ),
    )
    out = QuoteOut.model_validate(quote)
    out.lines = [QuoteLineOut.model_validate(ln) for ln in _load_lines(db, quote.id)]
    return out
