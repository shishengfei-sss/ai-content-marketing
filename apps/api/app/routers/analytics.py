from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Content, User
from app.schemas import AnalyticsStatsOut

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/stats", response_model=AnalyticsStatsOut)
def analytics_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant_id = current_user.tenant_id

    total_reads = (
        db.query(func.coalesce(func.sum(Content.mock_read_count), 0))
        .filter(Content.tenant_id == tenant_id, Content.status == "published")
        .scalar()
        or 0
    )

    total_generated = (
        db.query(func.count(Content.id)).filter(Content.tenant_id == tenant_id).scalar() or 0
    )

    published = (
        db.query(func.count(Content.id))
        .filter(Content.tenant_id == tenant_id, Content.status == "published")
        .scalar()
        or 0
    )
    failed = (
        db.query(func.count(Content.id))
        .filter(Content.tenant_id == tenant_id, Content.status == "failed")
        .scalar()
        or 0
    )
    attempts = published + failed
    success_rate = round(published / attempts * 100, 1) if attempts else 100.0

    platform_rows = (
        db.query(Content.platform, func.count(Content.id))
        .filter(Content.tenant_id == tenant_id)
        .group_by(Content.platform)
        .all()
    )
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
        count = (
            db.query(func.count(Content.id))
            .filter(
                Content.tenant_id == tenant_id,
                Content.created_at >= month_start,
                Content.created_at < next_month,
            )
            .scalar()
            or 0
        )
        monthly.append({"month": f"{month_start.month}月", "count": count})

    return AnalyticsStatsOut(
        total_reads=int(total_reads),
        total_generated=total_generated,
        publish_success_rate=success_rate,
        platform_breakdown=platform_breakdown,
        monthly_generation=monthly,
    )
