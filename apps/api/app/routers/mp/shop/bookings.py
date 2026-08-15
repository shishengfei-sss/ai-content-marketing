"""买家端预约 M10。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies_shop_buyer import BuyerContext, get_buyer_context
from app.schemas.shop_platform import (
    BookingCancelRequest,
    BookingCreateRequest,
    BookingListResponse,
    BookingOut,
)
from app.services.shop import fulfillment_service

router = APIRouter(prefix="/bookings", tags=["mp-shop-bookings"])


@router.post("", response_model=BookingOut)
def create(
    body: BookingCreateRequest,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return fulfillment_service.create_booking(db, bctx.buyer, body)


@router.get("", response_model=BookingListResponse)
def list_mine(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    items, total = fulfillment_service.list_bookings_buyer(
        db, bctx.buyer, page=page, page_size=page_size
    )
    return BookingListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel(
    booking_id: UUID,
    body: BookingCancelRequest | None = None,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return fulfillment_service.cancel_booking(
        db, bctx.buyer, booking_id, body or BookingCancelRequest()
    )
