"""产品计量单位 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_deals import ProductUnitCreate, ProductUnitOut, ProductUnitUpdate
from app.services.crm.product_unit_service import (
    create_unit,
    delete_unit,
    get_unit,
    list_units,
    seed_default_units,
    update_unit,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/product-units", tags=["crm-product-units"])


@router.get("", response_model=list[ProductUnitOut])
def get_units(
    active_only: bool = Query(default=False),
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    return [ProductUnitOut.model_validate(u) for u in list_units(db, ctx.tenant_id, active_only=active_only)]


@router.post("/seed-defaults", response_model=list[ProductUnitOut])
def post_seed_defaults(
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    created = seed_default_units(db, ctx)
    return [ProductUnitOut.model_validate(u) for u in created]


@router.post("", response_model=ProductUnitOut, status_code=201)
def post_unit(
    body: ProductUnitCreate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    unit = create_unit(db, ctx, body)
    return ProductUnitOut.model_validate(unit)


@router.patch("/{unit_id}", response_model=ProductUnitOut)
def patch_unit(
    unit_id: UUID,
    body: ProductUnitUpdate,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    unit = get_unit(db, ctx.tenant_id, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="计量单位不存在")
    unit = update_unit(db, ctx, unit, body)
    return ProductUnitOut.model_validate(unit)


@router.delete("/{unit_id}", status_code=204)
def delete_unit_endpoint(
    unit_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.product.manage")),
    db: Session = Depends(get_db),
):
    unit = get_unit(db, ctx.tenant_id, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="计量单位不存在")
    delete_unit(db, unit)
