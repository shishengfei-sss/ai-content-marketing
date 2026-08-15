"""A01 交易看板 API。对照 #a01 · GET /shop/analytics/*。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import AnalyticsSummaryOut, AnalyticsTrendsOut, OrderListResponse
from app.services.permission_service import require_permission
from app.services.shop import analytics_service

router = APIRouter(prefix="/analytics", tags=["shop-analytics"])


@router.get("/summary", response_model=AnalyticsSummaryOut)
def summary(
    range: str | None = Query(default="today"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.analytics.read")),
    db: Session = Depends(get_db),
):
    return analytics_service.get_summary(
        db, ctx, range_key=range, date_from=date_from, date_to=date_to, shop_id=shop_id
    )


@router.get("/trends", response_model=AnalyticsTrendsOut)
def trends(
    range: str | None = Query(default="today"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.analytics.read")),
    db: Session = Depends(get_db),
):
    return analytics_service.get_trends(
        db, ctx, range_key=range, date_from=date_from, date_to=date_to, shop_id=shop_id
    )


@router.get("/recent-orders", response_model=OrderListResponse)
def recent_orders(
    q: str | None = Query(default=None),
    source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=5, le=20),
    ctx: TenantContext = Depends(require_permission("shop.analytics.read")),
    db: Session = Depends(get_db),
):
    return analytics_service.list_recent_orders(
        db,
        ctx,
        shop_id=shop_id,
        q=q,
        source=source,
        status_filter=status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
