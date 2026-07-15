"""产品变体 + 价目表（v1.0 P1-I）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import PriceBook, PriceBookEntry, ProductVariant
from app.schemas.crm_deals import (
    PriceBookCreate,
    PriceBookEntryCreate,
    PriceBookUpdate,
    ProductVariantCreate,
    ProductVariantUpdate,
)
from app.services.crm.product_service import require_product


def list_variants(db: Session, ctx: TenantContext, product_id: UUID) -> list[ProductVariant]:
    require_product(db, ctx, product_id)
    return (
        db.query(ProductVariant)
        .filter(ProductVariant.tenant_id == ctx.tenant_id, ProductVariant.product_id == product_id)
        .order_by(ProductVariant.created_at.desc())
        .all()
    )


def create_variant(
    db: Session, ctx: TenantContext, product_id: UUID, data: ProductVariantCreate
) -> ProductVariant:
    require_product(db, ctx, product_id)
    sku = data.sku.strip()
    exists = (
        db.query(ProductVariant)
        .filter(ProductVariant.tenant_id == ctx.tenant_id, ProductVariant.sku == sku)
        .first()
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU 已存在")
    row = ProductVariant(
        tenant_id=ctx.tenant_id,
        product_id=product_id,
        sku=sku,
        variant_name=data.variant_name.strip(),
        attributes=data.attributes or {},
        list_price=data.list_price,
        cost_price=data.cost_price,
        is_active=data.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_variant(db: Session, tenant_id: UUID, variant_id: UUID) -> ProductVariant | None:
    return (
        db.query(ProductVariant)
        .filter(ProductVariant.id == variant_id, ProductVariant.tenant_id == tenant_id)
        .first()
    )


def update_variant(
    db: Session, ctx: TenantContext, row: ProductVariant, data: ProductVariantUpdate
) -> ProductVariant:
    require_product(db, ctx, row.product_id)
    if data.sku is not None and data.sku.strip() != row.sku:
        exists = (
            db.query(ProductVariant)
            .filter(
                ProductVariant.tenant_id == ctx.tenant_id,
                ProductVariant.sku == data.sku.strip(),
                ProductVariant.id != row.id,
            )
            .first()
        )
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU 已存在")
        row.sku = data.sku.strip()
    if data.variant_name is not None:
        row.variant_name = data.variant_name.strip()
    if data.attributes is not None:
        row.attributes = data.attributes
    if data.list_price is not None:
        row.list_price = data.list_price
    if data.cost_price is not None:
        row.cost_price = data.cost_price
    if data.is_active is not None:
        row.is_active = data.is_active
    db.commit()
    db.refresh(row)
    return row


def delete_variant(db: Session, row: ProductVariant) -> None:
    db.delete(row)
    db.commit()


def list_price_books(db: Session, ctx: TenantContext) -> list[PriceBook]:
    return (
        db.query(PriceBook)
        .filter(PriceBook.tenant_id == ctx.tenant_id)
        .order_by(PriceBook.created_at.desc())
        .all()
    )


def create_price_book(db: Session, ctx: TenantContext, data: PriceBookCreate) -> PriceBook:
    if data.is_default:
        db.query(PriceBook).filter(PriceBook.tenant_id == ctx.tenant_id, PriceBook.is_default.is_(True)).update(
            {"is_default": False}
        )
    row = PriceBook(
        tenant_id=ctx.tenant_id,
        name=data.name.strip(),
        description=data.description,
        is_default=data.is_default,
        is_active=data.is_active,
        created_by_user_id=ctx.user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_price_book(db: Session, tenant_id: UUID, book_id: UUID) -> PriceBook | None:
    return db.query(PriceBook).filter(PriceBook.id == book_id, PriceBook.tenant_id == tenant_id).first()


def require_price_book(db: Session, ctx: TenantContext, book_id: UUID) -> PriceBook:
    row = get_price_book(db, ctx.tenant_id, book_id)
    if not row:
        raise HTTPException(status_code=404, detail="价目表不存在")
    return row


def update_price_book(db: Session, ctx: TenantContext, row: PriceBook, data: PriceBookUpdate) -> PriceBook:
    if data.name is not None:
        row.name = data.name.strip()
    if data.description is not None:
        row.description = data.description
    if data.is_default is not None:
        if data.is_default:
            db.query(PriceBook).filter(
                PriceBook.tenant_id == ctx.tenant_id, PriceBook.is_default.is_(True), PriceBook.id != row.id
            ).update({"is_default": False})
        row.is_default = data.is_default
    if data.is_active is not None:
        row.is_active = data.is_active
    db.commit()
    db.refresh(row)
    return row


def delete_price_book(db: Session, row: PriceBook) -> None:
    db.delete(row)
    db.commit()


def list_entries(db: Session, ctx: TenantContext, book_id: UUID) -> list[PriceBookEntry]:
    require_price_book(db, ctx, book_id)
    return (
        db.query(PriceBookEntry)
        .filter(PriceBookEntry.tenant_id == ctx.tenant_id, PriceBookEntry.price_book_id == book_id)
        .order_by(PriceBookEntry.created_at.desc())
        .all()
    )


def list_product_entries(db: Session, ctx: TenantContext, product_id: UUID) -> list[PriceBookEntry]:
    require_product(db, ctx, product_id)
    return (
        db.query(PriceBookEntry)
        .filter(PriceBookEntry.tenant_id == ctx.tenant_id, PriceBookEntry.product_id == product_id)
        .order_by(PriceBookEntry.created_at.desc())
        .all()
    )


def create_entry(
    db: Session, ctx: TenantContext, book_id: UUID, data: PriceBookEntryCreate
) -> PriceBookEntry:
    require_price_book(db, ctx, book_id)
    require_product(db, ctx, data.product_id)
    if data.variant_id:
        v = get_variant(db, ctx.tenant_id, data.variant_id)
        if not v or v.product_id != data.product_id:
            raise HTTPException(status_code=400, detail="变体与产品不匹配")
    row = PriceBookEntry(
        tenant_id=ctx.tenant_id,
        price_book_id=book_id,
        product_id=data.product_id,
        variant_id=data.variant_id,
        unit_price=data.unit_price,
        min_quantity=data.min_quantity,
        valid_from=data.valid_from,
        valid_to=data.valid_to,
        customer_levels=data.customer_levels,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_entry(db: Session, ctx: TenantContext, entry_id: UUID) -> None:
    row = (
        db.query(PriceBookEntry)
        .filter(PriceBookEntry.id == entry_id, PriceBookEntry.tenant_id == ctx.tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="价目条目不存在")
    db.delete(row)
    db.commit()
