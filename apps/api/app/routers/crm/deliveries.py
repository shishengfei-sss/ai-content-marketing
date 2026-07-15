"""发货单独立操作 API。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_deals import DeliveryOut, DeliveryUpdate
from app.services.crm.delivery_service import (
    complete_delivery,
    require_delivery,
    ship_delivery,
    soft_delete_delivery,
    update_delivery,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/deliveries", tags=["crm-deliveries"])


@router.get("/{delivery_id}", response_model=DeliveryOut)
def get_delivery_endpoint(
    delivery_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.view")),
    db: Session = Depends(get_db),
):
    note = require_delivery(db, ctx, delivery_id)
    return DeliveryOut.model_validate(note)


@router.patch("/{delivery_id}", response_model=DeliveryOut)
def patch_delivery_endpoint(
    delivery_id: UUID,
    body: DeliveryUpdate,
    ctx: TenantContext = Depends(require_permission("crm.order.edit")),
    db: Session = Depends(get_db),
):
    note = require_delivery(db, ctx, delivery_id)
    note = update_delivery(db, ctx, note, body)
    return DeliveryOut.model_validate(note)


@router.post("/{delivery_id}/ship", response_model=DeliveryOut)
def ship_delivery_endpoint(
    delivery_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.edit")),
    db: Session = Depends(get_db),
):
    note = require_delivery(db, ctx, delivery_id)
    note = ship_delivery(db, ctx, note)
    return DeliveryOut.model_validate(note)


@router.post("/{delivery_id}/deliver", response_model=DeliveryOut)
def deliver_delivery_endpoint(
    delivery_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.edit")),
    db: Session = Depends(get_db),
):
    note = require_delivery(db, ctx, delivery_id)
    note = complete_delivery(db, ctx, note)
    return DeliveryOut.model_validate(note)


@router.delete("/{delivery_id}", status_code=204)
def delete_delivery_endpoint(
    delivery_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.edit")),
    db: Session = Depends(get_db),
):
    note = require_delivery(db, ctx, delivery_id)
    soft_delete_delivery(db, ctx, note)
