"""买家订单。对照 PRD 02-买家端UI.html #m11 #m12。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies_shop_buyer import BuyerContext, get_buyer_context
from app.schemas.shop_platform import (
    CreateOrderResponse,
    OrderCreateRequest,
    OrderListResponse,
    OrderOut,
    OrderRefundRequest,
    RefundListResponse,
    RefundOut,
)
from app.services.shop import order_service

router = APIRouter(prefix="/orders", tags=["mp-shop-orders"])


@router.post("", response_model=CreateOrderResponse)
def create_order(
    body: OrderCreateRequest,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return order_service.create_order(
        db, bctx.buyer, body.product_id, client_amount_cents=body.amount_cents
    )


@router.get("", response_model=OrderListResponse)
def list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="pending_payment|paid|refund|…"),
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    items, total = order_service.list_buyer_orders(
        db, bctx.buyer, page=page, page_size=page_size, status=status
    )
    return OrderListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: UUID,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return order_service.get_buyer_order(db, bctx.buyer, order_id)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: UUID,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    """M12-B 取消待付款。"""
    return order_service.buyer_cancel_order(db, bctx.buyer, order_id)


@router.post("/{order_id}/pay", response_model=CreateOrderResponse)
def continue_pay(
    order_id: UUID,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    """M11/M12 去支付（stub 模式直接付成功）。"""
    return order_service.buyer_continue_pay(db, bctx.buyer, order_id)


@router.post("/{order_id}/refund", response_model=RefundOut)
def refund_order(
    order_id: UUID,
    body: OrderRefundRequest,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return order_service.buyer_refund(db, bctx.buyer, order_id, body)


@router.get("/{order_id}/refunds", response_model=RefundListResponse)
def list_order_refunds(
    order_id: UUID,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    """M12-C 退款进度。"""
    items = order_service.list_buyer_order_refunds(db, bctx.buyer, order_id)
    return RefundListResponse(items=items, total=len(items), page=1, page_size=len(items) or 20)
