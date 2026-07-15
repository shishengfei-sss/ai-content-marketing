"""发货单服务（v1.0 P1）。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import DeliveryItem, DeliveryNote, OrderLine
from app.schemas.crm_deals import DeliveryCreate, DeliveryUpdate
from app.services.crm.number_service import generate_number
from app.services.crm.order_service import require_order


def get_delivery(db: Session, tenant_id: UUID, delivery_id: UUID) -> DeliveryNote | None:
    return (
        db.query(DeliveryNote)
        .filter(
            DeliveryNote.id == delivery_id,
            DeliveryNote.tenant_id == tenant_id,
            DeliveryNote.deleted_at.is_(None),
        )
        .first()
    )


def require_delivery(db: Session, ctx: TenantContext, delivery_id: UUID) -> DeliveryNote:
    d = get_delivery(db, ctx.tenant_id, delivery_id)
    if not d:
        raise HTTPException(status_code=404, detail="发货单不存在")
    require_order(db, ctx, d.order_id)
    return d


def list_order_deliveries(db: Session, ctx: TenantContext, order_id: UUID) -> list[DeliveryNote]:
    require_order(db, ctx, order_id)
    return (
        db.query(DeliveryNote)
        .filter(
            DeliveryNote.tenant_id == ctx.tenant_id,
            DeliveryNote.order_id == order_id,
            DeliveryNote.deleted_at.is_(None),
        )
        .order_by(DeliveryNote.created_at.desc())
        .all()
    )


def create_delivery(db: Session, ctx: TenantContext, order_id: UUID, data: DeliveryCreate) -> DeliveryNote:
    order = require_order(db, ctx, order_id)
    if order.status not in ("confirmed", "executing", "completed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"订单状态为 {order.status}，不可创建发货单",
        )
    note = DeliveryNote(
        tenant_id=ctx.tenant_id,
        order_id=order.id,
        delivery_number=generate_number(db, ctx.tenant_id, "delivery"),
        status="preparing",
        tracking_number=data.tracking_number,
        carrier=data.carrier,
        remark=data.remark,
        created_by_user_id=ctx.user.id,
    )
    db.add(note)
    db.flush()
    for it in data.items:
        line = (
            db.query(OrderLine)
            .filter(OrderLine.id == it.order_line_id, OrderLine.order_id == order.id)
            .first()
        )
        if not line:
            raise HTTPException(status_code=400, detail=f"订单行不存在: {it.order_line_id}")
        db.add(
            DeliveryItem(
                tenant_id=ctx.tenant_id,
                delivery_note_id=note.id,
                order_line_id=it.order_line_id,
                quantity=it.quantity,
            )
        )
    if order.status == "confirmed":
        order.status = "executing"
    db.commit()
    db.refresh(note)
    return note


def update_delivery(db: Session, ctx: TenantContext, note: DeliveryNote, data: DeliveryUpdate) -> DeliveryNote:
    if data.tracking_number is not None:
        note.tracking_number = data.tracking_number
    if data.carrier is not None:
        note.carrier = data.carrier
    if data.remark is not None:
        note.remark = data.remark
    if data.status is not None:
        note.status = data.status
    db.commit()
    db.refresh(note)
    return note


def ship_delivery(db: Session, ctx: TenantContext, note: DeliveryNote) -> DeliveryNote:
    if note.status not in ("preparing",):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"发货单状态为 {note.status}，不可发运")
    note.status = "shipped"
    note.shipped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(note)
    return note


def complete_delivery(db: Session, ctx: TenantContext, note: DeliveryNote) -> DeliveryNote:
    if note.status not in ("shipped", "preparing"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"发货单状态为 {note.status}，不可签收")
    now = datetime.now(timezone.utc)
    if note.status == "preparing":
        note.shipped_at = note.shipped_at or now
    note.status = "delivered"
    note.delivered_at = now
    db.commit()
    db.refresh(note)
    return note


def soft_delete_delivery(db: Session, ctx: TenantContext, note: DeliveryNote) -> None:
    note.deleted_at = datetime.now(timezone.utc)
    db.commit()
