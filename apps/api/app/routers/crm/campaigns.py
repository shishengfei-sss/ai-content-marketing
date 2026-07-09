"""营销活动 API。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.models.crm import MarketingCampaign
from app.schemas.crm import (
    CampaignContentLink,
    CampaignCreate,
    CampaignListResponse,
    CampaignOut,
    CampaignUpdate,
)
from app.services.crm.campaign_service import (
    campaign_to_out,
    create_campaign,
    link_content,
    require_campaign,
    soft_delete_campaign,
    unlink_content,
    update_campaign,
)
from app.services.crm.crm_scope_service import apply_campaign_list_scope, has_campaign_list_permission
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/campaigns", tags=["crm-campaigns"])


@router.get("", response_model=CampaignListResponse)
def list_campaigns(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.campaign.list_own",
            "crm.campaign.list_team",
            "crm.campaign.list_territory",
            "crm.campaign.list_all",
        )
    ),
    db: Session = Depends(get_db),
):
    if not has_campaign_list_permission(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
    query = db.query(MarketingCampaign).filter(
        MarketingCampaign.tenant_id == ctx.tenant_id,
        MarketingCampaign.deleted_at.is_(None),
    )
    query = apply_campaign_list_scope(query, ctx, db)
    if status:
        query = query.filter(MarketingCampaign.status == status)
    if q and q.strip():
        query = query.filter(MarketingCampaign.name.ilike(f"%{q.strip()}%"))
    total = query.count()
    items = (
        query.order_by(MarketingCampaign.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return CampaignListResponse(
        items=[CampaignOut.model_validate(campaign_to_out(db, ctx.tenant_id, i)) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=CampaignOut, status_code=201)
def post_campaign(
    body: CampaignCreate,
    ctx: TenantContext = Depends(require_permission("crm.campaign.create")),
    db: Session = Depends(get_db),
):
    campaign = create_campaign(db, ctx, body)
    return CampaignOut.model_validate(campaign_to_out(db, ctx.tenant_id, campaign))


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign_detail(
    campaign_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.campaign.view")),
    db: Session = Depends(get_db),
):
    campaign = require_campaign(db, ctx, campaign_id)
    return CampaignOut.model_validate(campaign_to_out(db, ctx.tenant_id, campaign))


@router.patch("/{campaign_id}", response_model=CampaignOut)
def patch_campaign(
    campaign_id: UUID,
    body: CampaignUpdate,
    ctx: TenantContext = Depends(require_permission("crm.campaign.edit")),
    db: Session = Depends(get_db),
):
    campaign = require_campaign(db, ctx, campaign_id)
    campaign = update_campaign(db, ctx, campaign, body)
    return CampaignOut.model_validate(campaign_to_out(db, ctx.tenant_id, campaign))


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(
    campaign_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.campaign.delete")),
    db: Session = Depends(get_db),
):
    campaign = require_campaign(db, ctx, campaign_id)
    soft_delete_campaign(db, campaign)


@router.post("/{campaign_id}/contents", status_code=201)
def add_campaign_content(
    campaign_id: UUID,
    body: CampaignContentLink,
    ctx: TenantContext = Depends(require_permission("crm.campaign.edit")),
    db: Session = Depends(get_db),
):
    campaign = require_campaign(db, ctx, campaign_id)
    link_content(db, ctx, campaign, body.content_id)
    return {"ok": True}


@router.delete("/{campaign_id}/contents/{content_id}", status_code=204)
def remove_campaign_content(
    campaign_id: UUID,
    content_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.campaign.edit")),
    db: Session = Depends(get_db),
):
    campaign = require_campaign(db, ctx, campaign_id)
    unlink_content(db, campaign, content_id)
