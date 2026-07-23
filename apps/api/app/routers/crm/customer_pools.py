"""客户公海 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import (
    CustomerOut,
    CustomerPoolClaimRequest,
    CustomerPoolCreate,
    CustomerPoolOut,
    CustomerPoolUpdate,
)
from app.services.crm import customer_pool_service
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/customer-pools", tags=["crm-customer-pools"])


@router.get("", response_model=list[CustomerPoolOut])
def api_list_pools(
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.customer.list_own",
            "crm.customer.list_team",
            "crm.customer.list_territory",
            "crm.customer.list_all",
        )
    ),
    db: Session = Depends(get_db),
):
    return customer_pool_service.list_pools(db, ctx.tenant_id)


@router.post("", response_model=CustomerPoolOut, status_code=201)
def api_create_pool(
    body: CustomerPoolCreate,
    ctx: TenantContext = Depends(require_permission("crm.customer.edit")),
    db: Session = Depends(get_db),
):
    return customer_pool_service.create_pool(
        db,
        ctx,
        name=body.name,
        territory_id=body.territory_id,
        industry_filter=body.industry_filter,
        auto_reclaim_days=body.auto_reclaim_days,
    )


@router.patch("/{pool_id}", response_model=CustomerPoolOut)
def api_update_pool(
    pool_id: UUID,
    body: CustomerPoolUpdate,
    ctx: TenantContext = Depends(require_permission("crm.customer.edit")),
    db: Session = Depends(get_db),
):
    pool = customer_pool_service.require_pool(db, ctx.tenant_id, pool_id)
    return customer_pool_service.update_pool(
        db,
        ctx,
        pool,
        name=body.name,
        territory_id=body.territory_id,
        industry_filter=body.industry_filter,
        auto_reclaim_days=body.auto_reclaim_days,
    )


@router.delete("/{pool_id}", status_code=204)
def api_delete_pool(
    pool_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.customer.edit")),
    db: Session = Depends(get_db),
):
    pool = customer_pool_service.require_pool(db, ctx.tenant_id, pool_id)
    customer_pool_service.delete_pool(db, ctx, pool)


@router.get("/{pool_id}/customers", response_model=list[CustomerOut])
def api_list_pool_customers(
    pool_id: UUID,
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.customer.list_own",
            "crm.customer.list_team",
            "crm.customer.list_territory",
            "crm.customer.list_all",
            "crm.customer.edit",
        )
    ),
    db: Session = Depends(get_db),
):
    return customer_pool_service.list_pool_customers(db, ctx, pool_id)


@router.post("/{pool_id}/claim", response_model=CustomerOut)
def api_claim_customer(
    pool_id: UUID,
    body: CustomerPoolClaimRequest,
    ctx: TenantContext = Depends(require_permission("crm.customer.edit")),
    db: Session = Depends(get_db),
):
    return customer_pool_service.claim_customer(db, ctx, pool_id, body.customer_id)
