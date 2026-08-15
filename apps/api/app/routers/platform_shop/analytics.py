"""P01 平台看板。对照 PRD 06#p01 · §8.14.1。"""

from __future__ import annotations

from datetime import date as DateOnly

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.permission_service import require_platform_shop_permission
from app.services.shop import p01_analytics_service as p01svc

router = APIRouter(prefix="/analytics", tags=["platform-shop-analytics"])

_read = require_platform_shop_permission("platform.shop.analytics")


class ExportDailyBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    day: DateOnly | None = Field(default=None, alias="date", description="日报日期，默认当天")


@router.get("/summary")
def summary(user: User = Depends(_read), db: Session = Depends(get_db)):
    return p01svc.get_summary(db, user)


@router.get("/trends")
def trends(
    range: str = Query(default="7d", alias="range"),
    user: User = Depends(_read),
    db: Session = Depends(get_db),
):
    return p01svc.get_trends(db, user, range)


@router.post("/export-daily")
def export_daily(
    body: ExportDailyBody | None = None,
    user: User = Depends(_read),
    db: Session = Depends(get_db),
):
    day = (body.day if body and body.day else DateOnly.today())
    csv_text = p01svc.export_daily_csv(db, user, day)
    payload = "\ufeff" + csv_text
    filename = f"shop-platform-daily-{day.isoformat()}.csv"
    return StreamingResponse(
        iter([payload.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
