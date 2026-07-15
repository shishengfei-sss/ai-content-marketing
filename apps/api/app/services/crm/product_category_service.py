"""产品分类服务（v1.0 P0）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Product, ProductCategory
from app.schemas.crm_deals import ProductCategoryCreate, ProductCategoryUpdate


def list_categories(
    db: Session, tenant_id: UUID, *, active_only: bool = False
) -> list[ProductCategory]:
    q = db.query(ProductCategory).filter(ProductCategory.tenant_id == tenant_id)
    if active_only:
        q = q.filter(ProductCategory.is_active.is_(True))
    return q.order_by(ProductCategory.sort_order.asc(), ProductCategory.name.asc()).all()


def get_category(db: Session, tenant_id: UUID, category_id: UUID) -> ProductCategory | None:
    return (
        db.query(ProductCategory)
        .filter(uuid_eq(ProductCategory.id, category_id), ProductCategory.tenant_id == tenant_id)
        .first()
    )


def create_category(
    db: Session, ctx: TenantContext, data: ProductCategoryCreate
) -> ProductCategory:
    if data.parent_id is not None:
        parent = get_category(db, ctx.tenant_id, data.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="父分类不存在")
    cat = ProductCategory(
        tenant_id=ctx.tenant_id,
        name=data.name.strip(),
        parent_id=data.parent_id,
        description=data.description,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def update_category(
    db: Session, ctx: TenantContext, cat: ProductCategory, data: ProductCategoryUpdate
) -> ProductCategory:
    if data.parent_id is not None:
        if data.parent_id == cat.id:
            raise HTTPException(status_code=400, detail="分类不能挂到自身")
        if data.parent_id:
            parent = get_category(db, ctx.tenant_id, data.parent_id)
            if not parent:
                raise HTTPException(status_code=404, detail="父分类不存在")
        cat.parent_id = data.parent_id or None
    if data.name is not None:
        cat.name = data.name.strip()
    if data.description is not None:
        cat.description = data.description
    if data.sort_order is not None:
        cat.sort_order = data.sort_order
    if data.is_active is not None:
        cat.is_active = data.is_active
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, cat: ProductCategory) -> None:
    # 子分类与产品解除关联后删除
    db.query(ProductCategory).filter(ProductCategory.parent_id == cat.id).update(
        {ProductCategory.parent_id: None}, synchronize_session=False
    )
    db.query(Product).filter(Product.category_id == cat.id).update(
        {Product.category_id: None}, synchronize_session=False
    )
    db.delete(cat)
    db.commit()
