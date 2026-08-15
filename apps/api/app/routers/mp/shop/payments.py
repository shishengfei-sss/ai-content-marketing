"""支付回调 / 查单（M3；真实微信证书依赖 B-M3）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies_shop_buyer import BuyerContext, get_buyer_context
from app.schemas.shop_platform import OrderOut, PaymentNotifyRequest
from app.services.shop import order_service

router = APIRouter(prefix="/payments", tags=["mp-shop-payments"])


class PaymentQueryRequest(BaseModel):
    order_id: UUID


@router.post("/notify", response_model=OrderOut)
def payment_notify(body: PaymentNotifyRequest, db: Session = Depends(get_db)):
    return order_service.apply_payment_notify(
        db,
        order_no=body.order_no,
        transaction_id=body.transaction_id,
        paid_amount_cents=body.paid_amount_cents,
        sign=body.sign,
    )


@router.post("/query", response_model=OrderOut)
def payment_query(
    body: PaymentQueryRequest,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return order_service.query_and_sync_payment(db, bctx.buyer, body.order_id)
