"""产品规格型号 API（v1.4）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_deals import ProductSpecModelCreate, ProductSpecModelOut, ProductSpecModelUpdate
from app.services.crm.product_spec_model_service import (
    create_spec_model,
    delete_spec_model,
    get_spec_model,
    list_spec_models,
    update_spec_model,
)
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/product-spec-models", tags=["crm-product-spec-models"])

_PRODUCT_READ = require_any_permission(
    "crm.product.manage",
    "crm.quote.create",
    "crm.quote.edit",
    "crm.order.create",
    "crm.order.edit",
    "crm.deal.create",
    "crm.deal.edit",
)


@router.get("", response_model=list[ProductSpecModelOut])
def get_spec_models(
    active_only: bool = Query(default=False),
    ctx: TenantContext = Depends(_PRODUCT_READ),
    db: Session = Depends(get_db),
):
    return [
        ProductSpecModelOut.model_validate(u)
        for u in list_spec_models(db, ctx.tenant_id, active_only=active_only)
    ]


@router.post("", response_model=ProductSpecModelOut, status_code=201)
def post_spec_model(
    body: ProductSpecModelCreate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return ProductSpecModelOut.model_validate(create_spec_model(db, ctx, body))


@router.patch("/{spec_id}", response_model=ProductSpecModelOut)
def patch_spec_model(
    spec_id: UUID,
    body: ProductSpecModelUpdate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    row = get_spec_model(db, ctx.tenant_id, spec_id)
    if not row:
        raise HTTPException(status_code=404, detail="规格型号不存在")
    return ProductSpecModelOut.model_validate(update_spec_model(db, ctx, row, body))


@router.delete("/{spec_id}", status_code=204)
def delete_spec_model_endpoint(
    spec_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    row = get_spec_model(db, ctx.tenant_id, spec_id)
    if not row:
        raise HTTPException(status_code=404, detail="规格型号不存在")
    delete_spec_model(db, row)
