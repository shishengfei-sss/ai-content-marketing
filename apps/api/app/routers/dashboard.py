from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Content, User
from app.schemas import DashboardStatsOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsOut)
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant_id = current_user.tenant_id
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    draft_count = (
        db.query(func.count(Content.id))
        .filter(Content.tenant_id == tenant_id, Content.status == "draft")
        .scalar()
        or 0
    )

    today_scheduled = (
        db.query(func.count(Content.id))
        .filter(
            Content.tenant_id == tenant_id,
            Content.status == "scheduled",
            Content.scheduled_at >= today_start,
            Content.scheduled_at < today_start + timedelta(days=1),
        )
        .scalar()
        or 0
    )

    reads_last_7_days = (
        db.query(func.coalesce(func.sum(Content.mock_read_count), 0))
        .filter(
            Content.tenant_id == tenant_id,
            Content.status == "published",
            Content.published_at >= week_start,
        )
        .scalar()
        or 0
    )

    generated_this_month = (
        db.query(func.count(Content.id))
        .filter(Content.tenant_id == tenant_id, Content.created_at >= month_start)
        .scalar()
        or 0
    )

    return DashboardStatsOut(
        draft_count=draft_count,
        pending_review=0,
        today_scheduled=today_scheduled,
        reads_last_7_days=int(reads_last_7_days),
        generated_this_month=generated_this_month,
    )
