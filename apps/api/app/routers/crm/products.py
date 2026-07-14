"""产品目录 API（v0.7 CRM-2）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_deals import (
    ProductCreate,
    ProductListResponse,
    ProductOut,
    ProductUpdate,
)
from app.services.crm.product_service import (
    create_product,
    require_product,
    search_products,
    soft_delete_product,
    update_product,
)
from app.services.crm.view_service import resolve_view_list_columns
from app.services.permission_service import require_permission

router = APIRouter(prefix="/products", tags=["crm-products"])


@router.get("", response_model=ProductListResponse)
def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    items, total = search_products(
        db, ctx.tenant_id, q=q, is_active=is_active, page=page, page_size=page_size
    )
    return ProductListResponse(
        items=[ProductOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        list_fields=resolve_view_list_columns(db, ctx.tenant_id, ctx.user.id, "product", None),
    )


@router.post("", response_model=ProductOut, status_code=201)
def post_product(
    body: ProductCreate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    p = create_product(db, ctx, body)
    return ProductOut.model_validate(p)


@router.get("/{product_id}", response_model=ProductOut)
def get_product_detail(
    product_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    p = require_product(db, ctx, product_id)
    return ProductOut.model_validate(p)


@router.patch("/{product_id}", response_model=ProductOut)
def patch_product(
    product_id: UUID,
    body: ProductUpdate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    p = require_product(db, ctx, product_id)
    p = update_product(db, ctx, p, body)
    return ProductOut.model_validate(p)


@router.delete("/{product_id}", status_code=204)
def delete_product_endpoint(
    product_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    p = require_product(db, ctx, product_id)
    soft_delete_product(db, p)
