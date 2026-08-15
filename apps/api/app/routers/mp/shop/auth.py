"""买家登录 / 绑定手机。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies_shop_buyer import BuyerContext, get_buyer_context
from app.schemas.shop_platform import (
    BuyerBindMobileRequest,
    BuyerLoginRequest,
    BuyerLoginResponse,
    BuyerOut,
)
from app.services.shop import buyer_service

router = APIRouter(prefix="/auth", tags=["mp-shop-auth"])


@router.post("/login", response_model=BuyerLoginResponse)
def login(body: BuyerLoginRequest, db: Session = Depends(get_db)):
    token, buyer = buyer_service.login_or_create(db, body.tenant_id, body.code)
    return BuyerLoginResponse(access_token=token, buyer=buyer_service.buyer_out(buyer))


@router.post("/bind", response_model=BuyerOut)
def bind_mobile(
    body: BuyerBindMobileRequest,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    buyer = buyer_service.bind_mobile(db, bctx.buyer, body.mobile)
    return buyer_service.buyer_out(buyer)


@router.get("/me", response_model=BuyerOut)
def me(bctx: BuyerContext = Depends(get_buyer_context)):
    return buyer_service.buyer_out(bctx.buyer)
