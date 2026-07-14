"""产品目录服务（v0.7 CRM-2）。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Product
from app.schemas.crm_deals import ProductCreate, ProductUpdate
from app.services.crm.number_service import generate_number
from app.services.crm.schema_service import validate_extra_data


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
    extra = validate_extra_data(db, ctx.tenant_id, "product", data.extra_data, is_create=True)
    product = Product(
        tenant_id=ctx.tenant_id,
        code=code,
        name=data.name.strip(),
        unit=data.unit,
        list_price=data.list_price,
        cost_price=data.cost_price,
        is_active=data.is_active,
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
        product.unit = data.unit
    if data.list_price is not None:
        product.list_price = data.list_price
    if data.cost_price is not None:
        product.cost_price = data.cost_price
    if data.is_active is not None:
        product.is_active = data.is_active
    if data.description is not None:
        product.description = data.description
    if data.extra_data is not None:
        merged = dict(product.extra_data or {})
        merged.update(data.extra_data)
        product.extra_data = validate_extra_data(db, ctx.tenant_id, "product", merged)
    db.commit()
    db.refresh(product)
    return product


def soft_delete_product(db: Session, product: Product) -> None:
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
