"""跟进 API。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import ActivityCreate, ActivityOut, ActivityUpdate, validate_activity_type
from app.services.crm.activity_service import (
    create_activity,
    delete_activity,
    list_activities,
    update_activity,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/activities", tags=["crm-activities"])


@router.get("", response_model=list[ActivityOut])
def get_activities(
    lead_id: UUID | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),
    deal_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("crm.activity.create")),
    db: Session = Depends(get_db),
):
    items = list_activities(db, ctx, lead_id=lead_id, customer_id=customer_id, deal_id=deal_id)
    return [ActivityOut.model_validate(i) for i in items]


@router.post("", response_model=ActivityOut, status_code=201)
def post_activity(
    body: ActivityCreate,
    ctx: TenantContext = Depends(require_permission("crm.activity.create")),
    db: Session = Depends(get_db),
):
    try:
        validate_activity_type(body.activity_type)
    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=str(e)) from e
    activity = create_activity(db, ctx, body)
    return ActivityOut.model_validate(activity)


@router.patch("/{activity_id}", response_model=ActivityOut)
def patch_activity(
    activity_id: UUID,
    body: ActivityUpdate,
    ctx: TenantContext = Depends(require_permission("crm.activity.create")),
    db: Session = Depends(get_db),
):
    try:
        if body.activity_type is not None:
            validate_activity_type(body.activity_type)
    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=str(e)) from e
    activity = update_activity(db, ctx, activity_id, body)
    return ActivityOut.model_validate(activity)


@router.delete("/{activity_id}", status_code=204)
def remove_activity(
    activity_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.activity.create")),
    db: Session = Depends(get_db),
):
    delete_activity(db, ctx, activity_id)
