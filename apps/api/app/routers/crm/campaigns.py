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
    CampaignPerformanceOut,
    CampaignUpdate,
    ChannelExecutionCreate,
    ChannelExecutionOut,
    ChannelExecutionUpdate,
)
from app.services.crm.campaign_performance_service import (
    calculate_campaign_performance,
    create_execution,
    delete_execution,
    get_execution,
    list_executions,
    update_execution,
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
from app.services.crm.filter_query import parse_list_filters_param
from app.services.crm.view_service import (
    apply_view_filters,
    apply_view_search,
    apply_view_sort,
    assert_can_access_view,
    get_view,
    resolve_view_list_columns,
)
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/campaigns", tags=["crm-campaigns"])


@router.get("", response_model=CampaignListResponse)
def list_campaigns(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    view_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    filters: str | None = Query(default=None, description="高级筛选 JSON"),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None, pattern="^(asc|desc)$"),
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

    active_view = None
    filters_applied = False
    if view_id is not None:
        active_view = get_view(db, ctx.tenant_id, view_id)
        if not active_view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, active_view)

    query = db.query(MarketingCampaign).filter(
        MarketingCampaign.tenant_id == ctx.tenant_id,
        MarketingCampaign.deleted_at.is_(None),
    )
    query = apply_campaign_list_scope(query, ctx, db)

    if active_view:
        query = apply_view_filters(query, db, ctx.tenant_id, "campaign", active_view.filters)
        query = apply_view_search(query, "campaign", active_view.search_q)
        query = apply_view_sort(query, "campaign", active_view.sort)
    else:
        parsed_filters = parse_list_filters_param(filters)
        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "campaign", parsed_filters)
            filters_applied = True
        elif status:
            query = query.filter(MarketingCampaign.status == status)
        query = apply_view_search(query, "campaign", q)
        sort_spec = None
        if sort_by:
            sort_spec = [{"field_key": sort_by, "dir": (sort_dir or "desc").lower()}]
        query = apply_view_sort(query, "campaign", sort_spec)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return CampaignListResponse(
        items=[CampaignOut.model_validate(campaign_to_out(db, ctx.tenant_id, i)) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        list_fields=resolve_view_list_columns(db, ctx.tenant_id, ctx.user.id, "campaign", active_view),
        view_id=active_view.id if active_view else None,
        filters_applied=filters_applied if filters else None,
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


@router.get("/{campaign_id}/channel-executions", response_model=list[ChannelExecutionOut])
def list_channel_executions(
    campaign_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.campaign.view")),
    db: Session = Depends(get_db),
):
    items = list_executions(db, ctx, campaign_id)
    return [ChannelExecutionOut.model_validate(i) for i in items]


@router.post("/{campaign_id}/channel-executions", response_model=ChannelExecutionOut, status_code=201)
def post_channel_execution(
    campaign_id: UUID,
    body: ChannelExecutionCreate,
    ctx: TenantContext = Depends(require_permission("crm.campaign.edit")),
    db: Session = Depends(get_db),
):
    row = create_execution(db, ctx, campaign_id, body)
    return ChannelExecutionOut.model_validate(row)


@router.patch("/channel-executions/{execution_id}", response_model=ChannelExecutionOut)
def patch_channel_execution(
    execution_id: UUID,
    body: ChannelExecutionUpdate,
    ctx: TenantContext = Depends(require_permission("crm.campaign.edit")),
    db: Session = Depends(get_db),
):
    row = get_execution(db, ctx.tenant_id, execution_id)
    if not row:
        raise HTTPException(status_code=404, detail="渠道执行不存在")
    row = update_execution(db, ctx, row, body)
    return ChannelExecutionOut.model_validate(row)


@router.delete("/channel-executions/{execution_id}", status_code=204)
def delete_channel_execution(
    execution_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.campaign.edit")),
    db: Session = Depends(get_db),
):
    row = get_execution(db, ctx.tenant_id, execution_id)
    if not row:
        raise HTTPException(status_code=404, detail="渠道执行不存在")
    delete_execution(db, ctx, row)


@router.get("/{campaign_id}/performance", response_model=CampaignPerformanceOut)
def get_campaign_performance(
    campaign_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.campaign.view")),
    db: Session = Depends(get_db),
):
    return calculate_campaign_performance(db, ctx, campaign_id)
