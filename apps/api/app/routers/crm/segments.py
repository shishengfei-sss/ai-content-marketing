"""客户细分 API（v1.0 P1-H）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import CustomerSegmentCreate, CustomerSegmentOut, CustomerSegmentUpdate
from app.services.crm.segment_service import (
    create_segment,
    delete_segment,
    list_segments,
    require_segment,
    update_segment,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/segments", tags=["crm-segments"])


@router.get("", response_model=list[CustomerSegmentOut])
def get_segments(
    ctx: TenantContext = Depends(require_permission("crm.campaign.view")),
    db: Session = Depends(get_db),
):
    return [CustomerSegmentOut.model_validate(i) for i in list_segments(db, ctx)]


@router.post("", response_model=CustomerSegmentOut, status_code=201)
def post_segment(
    body: CustomerSegmentCreate,
    ctx: TenantContext = Depends(require_permission("crm.campaign.edit")),
    db: Session = Depends(get_db),
):
    return CustomerSegmentOut.model_validate(create_segment(db, ctx, body))


@router.get("/{segment_id}", response_model=CustomerSegmentOut)
def get_segment_detail(
    segment_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.campaign.view")),
    db: Session = Depends(get_db),
):
    return CustomerSegmentOut.model_validate(require_segment(db, ctx, segment_id))


@router.patch("/{segment_id}", response_model=CustomerSegmentOut)
def patch_segment(
    segment_id: UUID,
    body: CustomerSegmentUpdate,
    ctx: TenantContext = Depends(require_permission("crm.campaign.edit")),
    db: Session = Depends(get_db),
):
    row = require_segment(db, ctx, segment_id)
    return CustomerSegmentOut.model_validate(update_segment(db, ctx, row, body))


@router.delete("/{segment_id}", status_code=204)
def remove_segment(
    segment_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.campaign.edit")),
    db: Session = Depends(get_db),
):
    row = require_segment(db, ctx, segment_id)
    delete_segment(db, row)
