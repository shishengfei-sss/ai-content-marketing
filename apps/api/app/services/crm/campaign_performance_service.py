"""营销渠道执行 + ROI（v1.0 P1-G）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import (
    CHANNEL_CONTENT_TYPES,
    CHANNEL_EXECUTION_STATUSES,
    CampaignChannelExecution,
    Lead,
    Order,
    Payment,
)
from app.schemas.crm import (
    CampaignChannelRoiOut,
    CampaignPerformanceOut,
    ChannelExecutionCreate,
    ChannelExecutionUpdate,
)
from app.services.crm.campaign_service import require_campaign


def _sync_campaign_spent(db: Session, campaign_id: UUID, tenant_id: UUID) -> float:
    from app.models.crm import MarketingCampaign

    rows = (
        db.query(CampaignChannelExecution)
        .filter(
            CampaignChannelExecution.tenant_id == tenant_id,
            CampaignChannelExecution.campaign_id == campaign_id,
        )
        .all()
    )
    total = round(sum(float(r.cost or 0) for r in rows), 2)
    camp = (
        db.query(MarketingCampaign)
        .filter(MarketingCampaign.id == campaign_id, MarketingCampaign.tenant_id == tenant_id)
        .first()
    )
    if camp:
        camp.spent = total
    return total


def list_executions(db: Session, ctx: TenantContext, campaign_id: UUID) -> list[CampaignChannelExecution]:
    require_campaign(db, ctx, campaign_id)
    return (
        db.query(CampaignChannelExecution)
        .filter(
            CampaignChannelExecution.tenant_id == ctx.tenant_id,
            CampaignChannelExecution.campaign_id == campaign_id,
        )
        .order_by(CampaignChannelExecution.created_at.desc())
        .all()
    )


def create_execution(
    db: Session, ctx: TenantContext, campaign_id: UUID, data: ChannelExecutionCreate
) -> CampaignChannelExecution:
    require_campaign(db, ctx, campaign_id)
    if data.content_type not in CHANNEL_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail=f"content_type 无效: {data.content_type}")
    if data.status not in CHANNEL_EXECUTION_STATUSES:
        raise HTTPException(status_code=422, detail=f"status 无效: {data.status}")
    row = CampaignChannelExecution(
        tenant_id=ctx.tenant_id,
        campaign_id=campaign_id,
        channel=data.channel.strip(),
        content_type=data.content_type,
        content_url=data.content_url,
        scheduled_at=data.scheduled_at,
        published_at=data.published_at,
        cost=data.cost,
        impressions=data.impressions,
        clicks=data.clicks,
        leads_generated=data.leads_generated,
        status=data.status,
        created_by_user_id=ctx.user.id,
    )
    db.add(row)
    db.flush()
    _sync_campaign_spent(db, campaign_id, ctx.tenant_id)
    db.commit()
    db.refresh(row)
    return row


def get_execution(db: Session, tenant_id: UUID, execution_id: UUID) -> CampaignChannelExecution | None:
    return (
        db.query(CampaignChannelExecution)
        .filter(CampaignChannelExecution.id == execution_id, CampaignChannelExecution.tenant_id == tenant_id)
        .first()
    )


def update_execution(
    db: Session, ctx: TenantContext, row: CampaignChannelExecution, data: ChannelExecutionUpdate
) -> CampaignChannelExecution:
    require_campaign(db, ctx, row.campaign_id)
    if data.channel is not None:
        row.channel = data.channel.strip()
    if data.content_type is not None:
        if data.content_type not in CHANNEL_CONTENT_TYPES:
            raise HTTPException(status_code=422, detail="content_type 无效")
        row.content_type = data.content_type
    if data.content_url is not None:
        row.content_url = data.content_url
    if data.scheduled_at is not None:
        row.scheduled_at = data.scheduled_at
    if data.published_at is not None:
        row.published_at = data.published_at
    if data.cost is not None:
        row.cost = data.cost
    if data.impressions is not None:
        row.impressions = data.impressions
    if data.clicks is not None:
        row.clicks = data.clicks
    if data.leads_generated is not None:
        row.leads_generated = data.leads_generated
    if data.status is not None:
        if data.status not in CHANNEL_EXECUTION_STATUSES:
            raise HTTPException(status_code=422, detail="status 无效")
        row.status = data.status
    _sync_campaign_spent(db, row.campaign_id, ctx.tenant_id)
    db.commit()
    db.refresh(row)
    return row


def delete_execution(db: Session, ctx: TenantContext, row: CampaignChannelExecution) -> None:
    campaign_id = row.campaign_id
    require_campaign(db, ctx, campaign_id)
    db.delete(row)
    db.flush()
    _sync_campaign_spent(db, campaign_id, ctx.tenant_id)
    db.commit()


def calculate_campaign_performance(db: Session, ctx: TenantContext, campaign_id: UUID) -> CampaignPerformanceOut:
    campaign = require_campaign(db, ctx, campaign_id)
    executions = list_executions(db, ctx, campaign_id)
    total_cost = round(sum(float(e.cost or 0) for e in executions), 2)
    total_clicks = sum(int(e.clicks or 0) for e in executions)

    leads = (
        db.query(Lead)
        .filter(Lead.tenant_id == ctx.tenant_id, Lead.campaign_id == campaign_id, Lead.deleted_at.is_(None))
        .all()
    )
    leads_count = len(leads)
    converted = [l for l in leads if l.status == "已转化" or l.converted_customer_id]
    customers_count = len(converted)
    customer_ids = [l.converted_customer_id for l in converted if l.converted_customer_id]

    revenue = 0.0
    if customer_ids:
        orders = (
            db.query(Order)
            .filter(
                Order.tenant_id == ctx.tenant_id,
                Order.customer_id.in_(customer_ids),
                Order.deleted_at.is_(None),
                Order.status.notin_(("draft", "cancelled", "superseded", "rejected")),
            )
            .all()
        )
        order_ids = [o.id for o in orders]
        if order_ids:
            pays = (
                db.query(Payment)
                .filter(
                    Payment.tenant_id == ctx.tenant_id,
                    Payment.order_id.in_(order_ids),
                    Payment.deleted_at.is_(None),
                    Payment.status == "confirmed",
                )
                .all()
            )
            revenue = round(sum(float(p.amount or 0) for p in pays), 2)
        else:
            revenue = round(sum(float(o.amount or 0) for o in orders), 2)

    cpl = round(total_cost / leads_count, 2) if leads_count else 0.0
    cpcust = round(total_cost / customers_count, 2) if customers_count else 0.0
    cpc = round(total_cost / total_clicks, 2) if total_clicks else 0.0
    roi = round((revenue - total_cost) / total_cost * 100, 2) if total_cost else 0.0
    conv = round(customers_count / leads_count * 100, 2) if leads_count else 0.0

    by_ch: dict[str, dict] = {}
    for e in executions:
        bucket = by_ch.setdefault(
            e.channel,
            {"cost": 0.0, "impressions": 0, "clicks": 0, "leads_generated": 0},
        )
        bucket["cost"] += float(e.cost or 0)
        bucket["impressions"] += int(e.impressions or 0)
        bucket["clicks"] += int(e.clicks or 0)
        bucket["leads_generated"] += int(e.leads_generated or 0)

    by_channel = []
    for ch, b in by_ch.items():
        ch_leads = b["leads_generated"] or 0
        by_channel.append(
            CampaignChannelRoiOut(
                channel=ch,
                cost=round(b["cost"], 2),
                impressions=b["impressions"],
                clicks=b["clicks"],
                leads_generated=ch_leads,
                cost_per_lead=round(b["cost"] / ch_leads, 2) if ch_leads else 0.0,
                roi=None,
            )
        )

    return CampaignPerformanceOut(
        campaign_id=campaign.id,
        total_cost=total_cost,
        budget=float(campaign.budget) if campaign.budget is not None else None,
        spent=float(campaign.spent or total_cost),
        leads_count=leads_count,
        customers_count=customers_count,
        revenue=revenue,
        cost_per_lead=cpl,
        cost_per_customer=cpcust,
        cost_per_click=cpc,
        roi=roi,
        conversion_rate=conv,
        by_channel=by_channel,
    )
