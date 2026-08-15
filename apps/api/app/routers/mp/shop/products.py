"""买家商品详情。对照 PRD §8.12.2 M03。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies_shop_buyer import BuyerContext, get_optional_buyer_context
from app.schemas.shop_platform import MpProductDetailOut
from app.services.shop import storefront_service

router = APIRouter(tags=["mp-shop-storefront"])


@router.get("/products/{product_id}", response_model=MpProductDetailOut)
def get_product(
    product_id: UUID,
    bctx: BuyerContext | None = Depends(get_optional_buyer_context),
    db: Session = Depends(get_db),
):
    buyer = None
    if bctx is not None:
        buyer = bctx.buyer
    return storefront_service.get_product_detail(db, product_id, buyer=buyer)
