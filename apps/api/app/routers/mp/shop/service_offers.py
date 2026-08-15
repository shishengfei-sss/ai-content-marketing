"""买家端服务时段 M10。"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies_shop_buyer import BuyerContext, get_buyer_context
from app.schemas.shop_platform import MpServiceSlotsResponse
from app.services.shop import service_offer_service

router = APIRouter(prefix="/service-offers", tags=["mp-shop-service-offers"])


@router.get("/{offer_id}/slots", response_model=MpServiceSlotsResponse)
def list_slots(
    offer_id: UUID,
    entitlement_id: UUID | None = Query(default=None),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return service_offer_service.mp_list_slots(
        db,
        bctx.buyer.tenant_id,
        offer_id,
        entitlement_id=entitlement_id,
        date_from=date_from,
        date_to=date_to,
    )
