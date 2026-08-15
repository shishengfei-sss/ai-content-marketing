"""抖店 Webhook（Stub 验签）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.shop_platform import DouyinOrderWebhookRequest, DouyinRefundWebhookRequest
from app.services.shop import channel_service

router = APIRouter(prefix="/douyin", tags=["webhooks-douyin"])


@router.post("/order")
def douyin_order(body: DouyinOrderWebhookRequest, db: Session = Depends(get_db)):
    return channel_service.handle_douyin_order(db, body)


@router.post("/refund")
def douyin_refund(body: DouyinRefundWebhookRequest, db: Session = Depends(get_db)):
    return channel_service.handle_douyin_refund(db, body)
