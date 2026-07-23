"""产品目录服务（v0.7 CRM-2）。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Order, OrderLine, Product, Quote, QuoteLine
from app.schemas.crm_deals import ProductCreate, ProductOut, ProductUpdate
from app.services.crm.number_service import generate_number
from app.services.crm.product_spec_model_service import assert_active_spec_model_id, get_spec_model
from app.services.crm.product_unit_service import assert_active_unit_name
from app.services.crm.schema_service import validate_extra_data


def product_to_out(db: Session, product: Product) -> ProductOut:
    out = ProductOut.model_validate(product)
    if product.spec_model_id:
        sm = get_spec_model(db, product.tenant_id, product.spec_model_id)
        out.spec_model_name = sm.name if sm else None
    return out


def get_product(db: Session, tenant_id: UUID, product_id: UUID) -> Product | None:
    return (
        db.query(Product)
        .filter(uuid_eq(Product.id, product_id), Product.tenant_id == tenant_id, Product.deleted_at.is_(None))
        .first()
    )


def require_product(db: Session, ctx: TenantContext, product_id: UUID) -> Product:
    p = get_product(db, ctx.tenant_id, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="产品不存在")
    return p


def _check_code_unique(db: Session, tenant_id: UUID, code: str, exclude_id: UUID | None = None) -> None:
    q = db.query(Product).filter(
        Product.tenant_id == tenant_id,
        Product.code == code,
        Product.deleted_at.is_(None),
    )
    if exclude_id is not None:
        q = q.filter(Product.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="产品编码已存在")


def create_product(db: Session, ctx: TenantContext, data: ProductCreate) -> Product:
    code = (data.code or "").strip() or generate_number(db, ctx.tenant_id, "product")
    _check_code_unique(db, ctx.tenant_id, code)
    unit = data.unit.strip() if data.unit else None
    assert_active_unit_name(db, ctx.tenant_id, unit)
    assert_active_spec_model_id(db, ctx.tenant_id, data.spec_model_id)
    extra = validate_extra_data(db, ctx.tenant_id, "product", data.extra_data, is_create=True)
    product = Product(
        tenant_id=ctx.tenant_id,
        code=code,
        name=data.name.strip(),
        unit=unit,
        list_price=data.list_price,
        cost_price=data.cost_price,
        default_tax_rate=data.default_tax_rate,
        price_includes_tax=bool(data.price_includes_tax),
        category_id=data.category_id,
        spec_model_id=data.spec_model_id,
        is_active=data.is_active,
        cpq_enabled=data.cpq_enabled,
        description=data.description,
        extra_data=extra,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, ctx: TenantContext, product: Product, data: ProductUpdate) -> Product:
    if data.code is not None and data.code != product.code:
        _check_code_unique(db, ctx.tenant_id, data.code, exclude_id=product.id)
        product.code = data.code.strip()
    if data.name is not None:
        product.name = data.name.strip()
    if data.unit is not None:
        unit = data.unit.strip() if data.unit else None
        assert_active_unit_name(db, ctx.tenant_id, unit)
        product.unit = unit
    if data.list_price is not None:
        product.list_price = data.list_price
    if data.cost_price is not None:
        product.cost_price = data.cost_price
    if "default_tax_rate" in data.model_fields_set:
        product.default_tax_rate = data.default_tax_rate
    if data.price_includes_tax is not None:
        product.price_includes_tax = data.price_includes_tax
    if "category_id" in data.model_fields_set:
        product.category_id = data.category_id
    if "spec_model_id" in data.model_fields_set:
        assert_active_spec_model_id(db, ctx.tenant_id, data.spec_model_id)
        product.spec_model_id = data.spec_model_id
    if data.is_active is not None:
        product.is_active = data.is_active
    if data.cpq_enabled is not None:
        product.cpq_enabled = data.cpq_enabled
    if data.description is not None:
        product.description = data.description
    if data.extra_data is not None:
        merged = dict(product.extra_data or {})
        merged.update(data.extra_data)
        product.extra_data = validate_extra_data(db, ctx.tenant_id, "product", merged)
    db.commit()
    db.refresh(product)
    return product


def _product_line_usage(db: Session, product: Product) -> tuple[int, int]:
    """返回 (未删除报价明细数, 未删除订单明细数)。"""
    quote_cnt = (
        db.query(QuoteLine)
        .join(Quote, Quote.id == QuoteLine.quote_id)
        .filter(
            uuid_eq(QuoteLine.product_id, product.id),
            Quote.tenant_id == product.tenant_id,
            Quote.deleted_at.is_(None),
        )
        .count()
    )
    order_cnt = (
        db.query(OrderLine)
        .join(Order, Order.id == OrderLine.order_id)
        .filter(
            uuid_eq(OrderLine.product_id, product.id),
            Order.tenant_id == product.tenant_id,
            Order.deleted_at.is_(None),
        )
        .count()
    )
    return quote_cnt, order_cnt


def soft_delete_product(db: Session, product: Product) -> None:
    quote_cnt, order_cnt = _product_line_usage(db, product)
    if quote_cnt or order_cnt:
        parts: list[str] = []
        if quote_cnt:
            parts.append(f"{quote_cnt} 条报价明细")
        if order_cnt:
            parts.append(f"{order_cnt} 条订单明细")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"产品已被{'、'.join(parts)}引用，无法删除（请改为停用）",
        )
    product.deleted_at = datetime.now(timezone.utc)
    db.commit()


def search_products(
    db: Session,
    tenant_id: UUID,
    *,
    q: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Product], int]:
    query = db.query(Product).filter(Product.tenant_id == tenant_id, Product.deleted_at.is_(None))
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(Product.name.like(pattern), Product.code.like(pattern)))
    if is_active is not None:
        query = query.filter(Product.is_active.is_(is_active))
    total = query.count()
    items = query.order_by(Product.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total
