"""线索公海 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import LeadOut, LeadPoolClaimRequest, LeadPoolCreate, LeadPoolOut, LeadPoolUpdate
from app.services.crm import lead_pool_service
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/lead-pools", tags=["crm-lead-pools"])


@router.get("", response_model=list[LeadPoolOut])
def api_list_pools(
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.lead.list_own",
            "crm.lead.list_team",
            "crm.lead.list_territory",
            "crm.lead.list_all",
        )
    ),
    db: Session = Depends(get_db),
):
    return lead_pool_service.list_pools(db, ctx.tenant_id)


@router.post("", response_model=LeadPoolOut, status_code=201)
def api_create_pool(
    body: LeadPoolCreate,
    ctx: TenantContext = Depends(require_permission("crm.lead.edit")),
    db: Session = Depends(get_db),
):
    return lead_pool_service.create_pool(
        db,
        ctx,
        name=body.name,
        territory_id=body.territory_id,
        industry_filter=body.industry_filter,
        auto_reclaim_days=body.auto_reclaim_days,
    )


@router.patch("/{pool_id}", response_model=LeadPoolOut)
def api_update_pool(
    pool_id: UUID,
    body: LeadPoolUpdate,
    ctx: TenantContext = Depends(require_permission("crm.lead.edit")),
    db: Session = Depends(get_db),
):
    pool = lead_pool_service.require_pool(db, ctx.tenant_id, pool_id)
    return lead_pool_service.update_pool(
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
    ctx: TenantContext = Depends(require_permission("crm.lead.edit")),
    db: Session = Depends(get_db),
):
    pool = lead_pool_service.require_pool(db, ctx.tenant_id, pool_id)
    lead_pool_service.delete_pool(db, ctx, pool)


@router.get("/{pool_id}/leads", response_model=list[LeadOut])
def api_list_pool_leads(
    pool_id: UUID,
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.lead.list_own",
            "crm.lead.list_team",
            "crm.lead.list_territory",
            "crm.lead.list_all",
            "crm.lead.edit",
        )
    ),
    db: Session = Depends(get_db),
):
    return lead_pool_service.list_pool_leads(db, ctx, pool_id)


@router.post("/{pool_id}/claim", response_model=LeadOut)
def api_claim_lead(
    pool_id: UUID,
    body: LeadPoolClaimRequest,
    ctx: TenantContext = Depends(require_permission("crm.lead.edit")),
    db: Session = Depends(get_db),
):
    return lead_pool_service.claim_lead(db, ctx, pool_id, body.lead_id)
