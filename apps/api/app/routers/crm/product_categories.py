"""产品分类 API（v1.0 P0）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_deals import (
    ProductCategoryCreate,
    ProductCategoryOut,
    ProductCategoryUpdate,
)
from app.services.crm.product_category_service import (
    create_category,
    delete_category,
    get_category,
    list_categories,
    update_category,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/product-categories", tags=["crm-product-categories"])


@router.get("", response_model=list[ProductCategoryOut])
def get_categories(
    active_only: bool = Query(default=False),
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return [
        ProductCategoryOut.model_validate(c)
        for c in list_categories(db, ctx.tenant_id, active_only=active_only)
    ]


@router.post("", response_model=ProductCategoryOut, status_code=201)
def post_category(
    body: ProductCategoryCreate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    cat = create_category(db, ctx, body)
    return ProductCategoryOut.model_validate(cat)


@router.patch("/{category_id}", response_model=ProductCategoryOut)
def patch_category(
    category_id: UUID,
    body: ProductCategoryUpdate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    cat = get_category(db, ctx.tenant_id, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="产品分类不存在")
    cat = update_category(db, ctx, cat, body)
    return ProductCategoryOut.model_validate(cat)


@router.delete("/{category_id}", status_code=204)
def delete_category_endpoint(
    category_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    cat = get_category(db, ctx.tenant_id, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="产品分类不存在")
    delete_category(db, cat)
