"""商家端退款列表。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import RefundListResponse, RefundOut
from app.services.permission_service import require_permission
from app.services.shop import order_service

router = APIRouter(prefix="/refunds", tags=["shop-refunds"])


@router.get("", response_model=RefundListResponse)
def list_refunds(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ctx: TenantContext = Depends(require_permission("shop.order.refund")),
    db: Session = Depends(get_db),
):
    items, total = order_service.list_refunds(db, ctx, page=page, page_size=page_size)
    return RefundListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/{refund_id}/replay-notify", response_model=RefundOut)
def replay_notify(
    refund_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.order.refund")),
    db: Session = Depends(get_db),
):
    """验收用：重复退款成功回调幂等。"""
    out = order_service.replay_refund_success(db, refund_id)
    if out.tenant_id != ctx.tenant_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="退款单不存在")
    return out
