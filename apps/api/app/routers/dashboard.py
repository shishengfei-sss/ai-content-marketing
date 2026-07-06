from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext, get_tenant_context
from app.models import Content
from app.schemas import DashboardStatsOut
from app.services.scope_service import apply_stats_scope

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsOut)
def get_stats(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    tenant_id = ctx.tenant_id
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    base = db.query(Content).filter(Content.tenant_id == tenant_id)
    base = apply_stats_scope(base, ctx, "dashboard.view_all")

    draft_count = base.filter(Content.status == "draft").count()

    today_scheduled = base.filter(
        Content.status == "scheduled",
        Content.scheduled_at >= today_start,
        Content.scheduled_at < today_start + timedelta(days=1),
    ).count()

    reads_last_7_days = (
        db.query(func.coalesce(func.sum(Content.mock_read_count), 0))
        .filter(
            Content.tenant_id == tenant_id,
            Content.status == "published",
            Content.published_at >= week_start,
        )
    )
    if "dashboard.view_all" not in {p.permission_code for p in ctx.membership.role.permissions}:
        reads_last_7_days = reads_last_7_days.filter(Content.author_id == ctx.user.id)
    reads_last_7_days = reads_last_7_days.scalar() or 0

    generated_this_month = base.filter(Content.created_at >= month_start).count()

    return DashboardStatsOut(
        draft_count=draft_count,
        pending_review=0,
        today_scheduled=today_scheduled,
        reads_last_7_days=int(reads_last_7_days),
        generated_this_month=generated_this_month,
    )
