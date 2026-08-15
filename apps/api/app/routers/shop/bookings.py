"""商家端预约名单。对照 PRD 01-管理端UI.html #a07a · #a11a-bookings。"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.permissions import membership_is_shop_clerk
from app.schemas.shop_platform import (
    BookingExportRequest,
    BookingListResponse,
    BookingOut,
    ShopExportTaskOut,
)
from app.services.permission_service import require_permission
from app.services.shop import fulfillment_service

router = APIRouter(prefix="/bookings", tags=["shop-bookings"])


def _forbid_clerk(ctx: TenantContext) -> None:
    if membership_is_shop_clerk(ctx.membership):
        raise HTTPException(status_code=403, detail="店员仅可访问核销台")


@router.get("", response_model=BookingListResponse)
def list_bookings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    booked_date: date | None = Query(default=None),
    booked_from: date | None = Query(default=None),
    booked_to: date | None = Query(default=None),
    buyer_id: UUID | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    _forbid_clerk(ctx)
    items, total, counts = fulfillment_service.list_bookings_merchant(
        db,
        ctx,
        page=page,
        page_size=page_size,
        booked_date=booked_date,
        booked_from=booked_from,
        booked_to=booked_to,
        buyer_id=buyer_id,
        shop_id=shop_id,
        status=status,
        q=q,
    )
    return BookingListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        status_counts=counts,
    )


@router.get("/export")
def export_bookings(
    booked_date: date | None = Query(default=None),
    booked_from: date | None = Query(default=None),
    booked_to: date | None = Query(default=None),
    buyer_id: UUID | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    _forbid_clerk(ctx)
    csv_text = fulfillment_service.export_bookings_csv(
        db,
        ctx,
        booked_date=booked_date,
        booked_from=booked_from,
        booked_to=booked_to,
        buyer_id=buyer_id,
        shop_id=shop_id,
        status=status,
        q=q,
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-bookings.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_booking_export_task(
    body: BookingExportRequest | None = None,
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    """对照 #a07a · #a11a-bookings · 04#select-common：预约名单异步导出（站内信本批不接）。"""
    _forbid_clerk(ctx)
    return fulfillment_service.create_booking_export_task(db, ctx, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_booking_export_task(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    _forbid_clerk(ctx)
    return fulfillment_service.get_booking_export_task(db, ctx, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_booking_export_file(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    _forbid_clerk(ctx)
    csv_text = fulfillment_service.read_booking_export_file(db, ctx, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-bookings.csv"'},
    )


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    _forbid_clerk(ctx)
    return fulfillment_service.get_booking_merchant(db, ctx, booking_id)
