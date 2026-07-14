from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext, get_tenant_context
from app.models import Content
from app.schemas import AnalyticsStatsOut
from app.services.scope_service import apply_stats_scope
from app.services.crm.deal_report_service import deal_funnel_report, deal_forecast_report, deal_win_loss_report

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/stats", response_model=AnalyticsStatsOut)
def analytics_stats(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    tenant_id = ctx.tenant_id
    perms = {p.permission_code for p in ctx.membership.role.permissions}
    view_all = "analytics.view_all" in perms

    base = db.query(Content).filter(Content.tenant_id == tenant_id)
    base = apply_stats_scope(base, ctx, "analytics.view_all")

    total_reads = (
        db.query(func.coalesce(func.sum(Content.mock_read_count), 0))
        .filter(Content.tenant_id == tenant_id, Content.status == "published")
    )
    if not view_all:
        total_reads = total_reads.filter(Content.author_id == ctx.user.id)
    total_reads = int(total_reads.scalar() or 0)

    total_generated = base.count()

    published = base.filter(Content.status == "published").count()
    failed = base.filter(Content.status == "failed").count()
    attempts = published + failed
    success_rate = round(published / attempts * 100, 1) if attempts else 100.0

    platform_rows = (
        db.query(Content.platform, func.count(Content.id))
        .filter(Content.tenant_id == tenant_id)
    )
    if not view_all:
        platform_rows = platform_rows.filter(Content.author_id == ctx.user.id)
    platform_rows = platform_rows.group_by(Content.platform).all()
    platform_breakdown = {row[0]: row[1] for row in platform_rows}

    now = datetime.now(timezone.utc)
    monthly: list[dict[str, int | str]] = []
    for i in range(5, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 28)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        count = base.filter(
            Content.created_at >= month_start,
            Content.created_at < next_month,
        ).count()
        monthly.append({"month": f"{month_start.month}月", "count": count})

    return AnalyticsStatsOut(
        total_reads=total_reads,
        total_generated=total_generated,
        publish_success_rate=success_rate,
        platform_breakdown=platform_breakdown,
        monthly_generation=monthly,
    )


@router.get("/deal-funnel")
def deal_funnel_endpoint(
    pipeline_id: UUID | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    return deal_funnel_report(
        db, ctx, pipeline_id=pipeline_id, owner_id=owner_id,
        start_date=start_date, end_date=end_date,
    )


@router.get("/deal-forecast")
def deal_forecast_endpoint(
    pipeline_id: UUID | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    return deal_forecast_report(db, ctx, pipeline_id=pipeline_id, owner_id=owner_id)


@router.get("/deal-win-loss")
def deal_win_loss_endpoint(
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    return deal_win_loss_report(db, ctx, start_date=start_date, end_date=end_date)
