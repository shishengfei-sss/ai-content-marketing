"""退款服务（v1.0 P1-F）。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import Payment, Refund
from app.schemas.crm_deals import RefundCreate
from app.services.crm.number_service import generate_number
from app.services.crm.order_service import require_order


def list_order_refunds(db: Session, ctx: TenantContext, order_id: UUID) -> list[Refund]:
    require_order(db, ctx, order_id)
    return (
        db.query(Refund)
        .filter(
            Refund.tenant_id == ctx.tenant_id,
            Refund.order_id == order_id,
            Refund.deleted_at.is_(None),
        )
        .order_by(Refund.created_at.desc())
        .all()
    )


def create_refund(db: Session, ctx: TenantContext, data: RefundCreate) -> Refund:
    order = require_order(db, ctx, data.order_id)
    if order.status in ("draft", "cancelled", "superseded"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"订单状态 {order.status} 不可退款")
    if data.original_payment_id:
        pay = (
            db.query(Payment)
            .filter(
                Payment.id == data.original_payment_id,
                Payment.tenant_id == ctx.tenant_id,
                Payment.deleted_at.is_(None),
            )
            .first()
        )
        if not pay:
            raise HTTPException(status_code=404, detail="原回款不存在")
        if pay.order_id != order.id:
            raise HTTPException(status_code=400, detail="回款与订单不匹配")
    refund = Refund(
        tenant_id=ctx.tenant_id,
        order_id=order.id,
        original_payment_id=data.original_payment_id,
        refund_number=generate_number(db, ctx.tenant_id, "refund"),
        amount=data.amount,
        reason=data.reason,
        status="pending",
        created_by_user_id=ctx.user.id,
    )
    db.add(refund)
    db.commit()
    db.refresh(refund)
    return refund


def get_refund(db: Session, tenant_id: UUID, refund_id: UUID) -> Refund | None:
    return (
        db.query(Refund)
        .filter(Refund.id == refund_id, Refund.tenant_id == tenant_id, Refund.deleted_at.is_(None))
        .first()
    )


def require_refund(db: Session, ctx: TenantContext, refund_id: UUID) -> Refund:
    r = get_refund(db, ctx.tenant_id, refund_id)
    if not r:
        raise HTTPException(status_code=404, detail="退款单不存在")
    require_order(db, ctx, r.order_id)
    return r


def approve_refund(db: Session, ctx: TenantContext, refund: Refund) -> Refund:
    if refund.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"状态为 {refund.status}，不可批准")
    refund.status = "approved"
    refund.approved_by_user_id = ctx.user.id
    refund.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(refund)
    return refund


def complete_refund(db: Session, ctx: TenantContext, refund: Refund) -> Refund:
    if refund.status not in ("pending", "approved"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"状态为 {refund.status}，不可完成")
    if refund.status == "pending":
        refund.approved_by_user_id = ctx.user.id
        refund.approved_at = datetime.now(timezone.utc)
    refund.status = "completed"
    db.commit()
    db.refresh(refund)
    return refund


def reject_refund(db: Session, ctx: TenantContext, refund: Refund) -> Refund:
    if refund.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"状态为 {refund.status}，不可驳回")
    refund.status = "rejected"
    refund.approved_by_user_id = ctx.user.id
    refund.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(refund)
    return refund
