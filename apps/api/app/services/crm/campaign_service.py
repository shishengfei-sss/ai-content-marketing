"""营销活动 CRUD 与内容关联。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import Content
from app.models.crm import CampaignContent, CrmTask, Lead, MarketingCampaign
from app.schemas.crm import (
    CampaignCreate,
    CampaignUpdate,
    validate_campaign_status,
    validate_campaign_type,
)
from app.services.crm.crm_scope_service import assert_can_view_campaign
from app.services.crm.number_service import generate_number
from app.services.crm.sales_org_service import apply_creator_org_defaults, apply_owner_org_snapshot, assert_can_assign_owner


def _perm_set(ctx: TenantContext) -> set[str]:
    return {p.permission_code for p in ctx.membership.role.permissions}


def get_campaign(db: Session, tenant_id: UUID, campaign_id: UUID) -> MarketingCampaign | None:
    return (
        db.query(MarketingCampaign)
        .filter(
            uuid_eq(MarketingCampaign.id, campaign_id),
            MarketingCampaign.tenant_id == tenant_id,
            MarketingCampaign.deleted_at.is_(None),
        )
        .first()
    )


def _counts(db: Session, tenant_id: UUID, campaign_id: UUID) -> tuple[int, int, int]:
    lead_count = (
        db.query(Lead)
        .filter(
            Lead.tenant_id == tenant_id,
            Lead.campaign_id == campaign_id,
            Lead.deleted_at.is_(None),
        )
        .count()
    )
    task_count = (
        db.query(CrmTask)
        .filter(
            CrmTask.tenant_id == tenant_id,
            CrmTask.campaign_id == campaign_id,
            CrmTask.deleted_at.is_(None),
        )
        .count()
    )
    content_count = (
        db.query(CampaignContent)
        .filter(CampaignContent.campaign_id == campaign_id)
        .count()
    )
    return lead_count, task_count, content_count


def campaign_to_out(db: Session, tenant_id: UUID, campaign: MarketingCampaign) -> dict:
    lead_count, task_count, content_count = _counts(db, tenant_id, campaign.id)
    return {
        "id": campaign.id,
        "campaign_number": campaign.campaign_number,
        "name": campaign.name,
        "status": campaign.status,
        "start_at": campaign.start_at,
        "end_at": campaign.end_at,
        "goal": campaign.goal,
        "channels": campaign.channels or [],
        "description": campaign.description,
        "campaign_type": campaign.campaign_type,
        "expected_leads": campaign.expected_leads,
        "location": campaign.location,
        "budget": float(campaign.budget) if campaign.budget is not None else None,
        "spent": float(campaign.spent or 0),
        "currency": campaign.currency or "CNY",
        "target_segment_id": campaign.target_segment_id,
        "owner_user_id": campaign.owner_user_id,
        "territory_id": campaign.territory_id,
        "created_at": campaign.created_at,
        "updated_at": campaign.updated_at,
        "lead_count": lead_count,
        "task_count": task_count,
        "content_count": content_count,
    }


def create_campaign(db: Session, ctx: TenantContext, data: CampaignCreate) -> MarketingCampaign:
    validate_campaign_status(data.status)
    try:
        validate_campaign_type(data.campaign_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    owner_id = data.owner_user_id or ctx.user.id
    if owner_id != ctx.user.id:
        assert_can_assign_owner(db, ctx, owner_id)
    territory_id, manager_user_id = apply_creator_org_defaults(db, ctx, territory_id=data.territory_id)
    campaign = MarketingCampaign(
        tenant_id=ctx.tenant_id,
        campaign_number=generate_number(db, ctx.tenant_id, "campaign"),
        name=data.name.strip(),
        status=data.status,
        start_at=data.start_at,
        end_at=data.end_at,
        goal=data.goal,
        channels=data.channels or [],
        description=data.description,
        campaign_type=data.campaign_type or None,
        expected_leads=data.expected_leads,
        location=(data.location.strip() if data.location else None),
        budget=data.budget,
        spent=data.spent if data.spent is not None else 0,
        currency=data.currency or "CNY",
        target_segment_id=data.target_segment_id,
        owner_user_id=owner_id,
        territory_id=territory_id,
        manager_user_id=manager_user_id,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


ALLOWED_CAMPAIGN_STATUS_TRANSITIONS = {
    "draft": {"active"},
    "active": {"paused", "ended"},
    "paused": {"active", "ended"},
    "ended": set(),
}


def update_campaign(
    db: Session, ctx: TenantContext, campaign: MarketingCampaign, data: CampaignUpdate
) -> MarketingCampaign:
    perms = _perm_set(ctx)
    fields = data.model_fields_set
    # 已结束：禁止改内容；不可再变更状态
    if campaign.status == "ended":
        if fields and fields != {"status"}:
            raise HTTPException(status_code=400, detail="已结束的活动不可编辑")
        if "status" in fields and data.status != "ended":
            raise HTTPException(status_code=400, detail="已结束的活动不可再变更状态")
        return campaign
    if data.owner_user_id is not None and data.owner_user_id != campaign.owner_user_id:
        if "crm.campaign.manage" not in perms and "crm.campaign.edit" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限修改负责人")
        assert_can_assign_owner(db, ctx, data.owner_user_id)
        campaign.owner_user_id = data.owner_user_id
        snap_territory, snap_manager = apply_owner_org_snapshot(db, ctx.tenant_id, data.owner_user_id)
        if data.territory_id is None:
            campaign.territory_id = snap_territory
        campaign.manager_user_id = snap_manager
    if data.name is not None:
        campaign.name = data.name.strip()
    if data.status is not None:
        validate_campaign_status(data.status)
        if data.status != campaign.status:
            if "crm.campaign.manage" not in perms:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限管理活动状态")
            allowed = ALLOWED_CAMPAIGN_STATUS_TRANSITIONS.get(campaign.status, set())
            if data.status not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail=f"不允许从「{campaign.status}」变更为「{data.status}」，请使用启动/暂停/恢复/结束操作",
                )
            campaign.status = data.status
    if data.start_at is not None:
        campaign.start_at = data.start_at
    if data.end_at is not None:
        campaign.end_at = data.end_at
    if data.goal is not None:
        campaign.goal = data.goal
    if data.channels is not None:
        campaign.channels = data.channels
    if data.description is not None:
        campaign.description = data.description
    if "campaign_type" in fields:
        try:
            validate_campaign_type(data.campaign_type)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        campaign.campaign_type = data.campaign_type or None
    if "expected_leads" in fields:
        campaign.expected_leads = data.expected_leads
    if "location" in fields:
        campaign.location = data.location.strip() if data.location else None
    if "territory_id" in fields:
        campaign.territory_id = data.territory_id
    if "budget" in fields:
        campaign.budget = data.budget
    if data.spent is not None:
        campaign.spent = data.spent
    if data.currency is not None:
        campaign.currency = data.currency
    if "target_segment_id" in fields:
        campaign.target_segment_id = data.target_segment_id
    db.commit()
    db.refresh(campaign)
    return campaign


def soft_delete_campaign(db: Session, campaign: MarketingCampaign) -> None:
    if campaign.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态的活动可删除")
    campaign.deleted_at = datetime.now(timezone.utc)
    db.commit()


def require_campaign(db: Session, ctx: TenantContext, campaign_id: UUID) -> MarketingCampaign:
    campaign = get_campaign(db, ctx.tenant_id, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="活动不存在")
    assert_can_view_campaign(
        ctx,
        db,
        campaign.owner_user_id,
        campaign.territory_id,
        manager_user_id=getattr(campaign, "manager_user_id", None),
    )
    return campaign


def link_content(db: Session, ctx: TenantContext, campaign: MarketingCampaign, content_id: UUID) -> None:
    content = (
        db.query(Content)
        .filter(Content.id == content_id, Content.tenant_id == ctx.tenant_id)
        .first()
    )
    if not content:
        raise HTTPException(status_code=404, detail="内容不存在")
    exists = (
        db.query(CampaignContent)
        .filter(
            CampaignContent.campaign_id == campaign.id,
            CampaignContent.content_id == content_id,
        )
        .first()
    )
    if exists:
        return
    db.add(CampaignContent(campaign_id=campaign.id, content_id=content_id))
    db.commit()


def unlink_content(db: Session, campaign: MarketingCampaign, content_id: UUID) -> None:
    row = (
        db.query(CampaignContent)
        .filter(
            CampaignContent.campaign_id == campaign.id,
            CampaignContent.content_id == content_id,
        )
        .first()
    )
    if row:
        db.delete(row)
        db.commit()
