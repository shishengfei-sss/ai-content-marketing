"""营销活动投放渠道字典 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import CampaignChannelCreate, CampaignChannelOut, CampaignChannelUpdate
from app.services.crm.campaign_channel_service import (
    create_channel,
    delete_channel,
    get_channel,
    list_channels,
    seed_default_channels,
    update_channel,
)
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/campaign-channels", tags=["crm-campaign-channels"])

_READ_PERMS = (
    "crm.campaign.view",
    "crm.campaign.create",
    "crm.campaign.edit",
    "crm.campaign.manage",
    "crm.campaign.list_own",
    "crm.campaign.list_team",
    "crm.campaign.list_territory",
    "crm.campaign.list_all",
)


@router.get("", response_model=list[CampaignChannelOut])
def get_channels(
    active_only: bool = Query(default=False),
    ctx: TenantContext = Depends(require_any_permission(*_READ_PERMS)),
    db: Session = Depends(get_db),
):
    return [
        CampaignChannelOut.model_validate(c)
        for c in list_channels(db, ctx.tenant_id, active_only=active_only)
    ]


@router.post("/seed-defaults", response_model=list[CampaignChannelOut])
def post_seed_defaults(
    ctx: TenantContext = Depends(require_permission("crm.campaign.manage")),
    db: Session = Depends(get_db),
):
    created = seed_default_channels(db, ctx)
    return [CampaignChannelOut.model_validate(c) for c in created]


@router.post("", response_model=CampaignChannelOut, status_code=201)
def post_channel(
    body: CampaignChannelCreate,
    ctx: TenantContext = Depends(require_permission("crm.campaign.manage")),
    db: Session = Depends(get_db),
):
    return CampaignChannelOut.model_validate(create_channel(db, ctx, body))


@router.patch("/{channel_id}", response_model=CampaignChannelOut)
def patch_channel(
    channel_id: UUID,
    body: CampaignChannelUpdate,
    ctx: TenantContext = Depends(require_permission("crm.campaign.manage")),
    db: Session = Depends(get_db),
):
    row = get_channel(db, ctx.tenant_id, channel_id)
    if not row:
        raise HTTPException(status_code=404, detail="投放渠道不存在")
    return CampaignChannelOut.model_validate(update_channel(db, ctx, row, body))


@router.delete("/{channel_id}", status_code=204)
def delete_channel_endpoint(
    channel_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.campaign.manage")),
    db: Session = Depends(get_db),
):
    row = get_channel(db, ctx.tenant_id, channel_id)
    if not row:
        raise HTTPException(status_code=404, detail="投放渠道不存在")
    delete_channel(db, row)
