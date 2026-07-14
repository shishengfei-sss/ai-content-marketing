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


@router.post("/{pool_id}/claim", response_model=CustomerOut)
def api_claim_customer(
    pool_id: UUID,
    body: CustomerPoolClaimRequest,
    ctx: TenantContext = Depends(require_permission("crm.customer.edit")),
    db: Session = Depends(get_db),
):
    return customer_pool_service.claim_customer(db, ctx, pool_id, body.customer_id)
