"""通知中心 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.services.crm import notification_service
from app.services.permission_service import require_any_permission

router = APIRouter(prefix="/notifications", tags=["crm-notifications"])


class NotificationOut(BaseModel):
    id: UUID
    category: str
    title: str
    body: str | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    is_read: bool
    created_at: object
    read_at: object | None = None

    model_config = {"from_attributes": True}


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    total: int
    unread: int
    page: int
    page_size: int


@router.get("", response_model=NotificationListOut)
def api_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    unread_only: bool = Query(default=False),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.lead.view",
            "crm.customer.view",
            "crm.deal.view",
            "crm.lead.list_own",
        )
    ),
    db: Session = Depends(get_db),
):
    items, total = notification_service.list_notifications(
        db, ctx, unread_only=unread_only, page=page, page_size=page_size
    )
    return NotificationListOut(
        items=[NotificationOut.model_validate(i) for i in items],
        total=total,
        unread=notification_service.unread_count(db, ctx),
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count")
def api_unread_count(
    ctx: TenantContext = Depends(
        require_any_permission("crm.lead.view", "crm.customer.view", "crm.deal.view", "crm.lead.list_own")
    ),
    db: Session = Depends(get_db),
):
    return {"count": notification_service.unread_count(db, ctx)}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def api_mark_read(
    notification_id: UUID,
    ctx: TenantContext = Depends(
        require_any_permission("crm.lead.view", "crm.customer.view", "crm.deal.view", "crm.lead.list_own")
    ),
    db: Session = Depends(get_db),
):
    return notification_service.mark_read(db, ctx, notification_id)


@router.post("/read-all")
def api_mark_all_read(
    ctx: TenantContext = Depends(
        require_any_permission("crm.lead.view", "crm.customer.view", "crm.deal.view", "crm.lead.list_own")
    ),
    db: Session = Depends(get_db),
):
    n = notification_service.mark_all_read(db, ctx)
    return {"updated": n}
