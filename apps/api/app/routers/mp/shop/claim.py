"""买家领权 M14。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies_shop_buyer import BuyerContext, get_buyer_context
from app.schemas.shop_platform import ClaimConfirmResponse, ClaimInfoOut
from app.services.shop import channel_service

router = APIRouter(prefix="/claim", tags=["mp-shop-claim"])


@router.get("/pending", response_model=ClaimInfoOut)
def get_pending_claim(
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return channel_service.get_pending_claim_for_buyer(db, bctx.buyer)


@router.get("/{token}", response_model=ClaimInfoOut)
def get_claim(token: str, db: Session = Depends(get_db)):
    return channel_service.get_claim_info(db, token)


@router.post("/{token}", response_model=ClaimConfirmResponse)
def confirm_claim(
    token: str,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return channel_service.confirm_claim(db, token, bctx.buyer)
