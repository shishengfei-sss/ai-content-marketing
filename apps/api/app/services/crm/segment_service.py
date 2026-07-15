"""客户细分（v1.0 P1-H）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import CustomerSegment
from app.schemas.crm import CustomerSegmentCreate, CustomerSegmentUpdate


def list_segments(db: Session, ctx: TenantContext) -> list[CustomerSegment]:
    return (
        db.query(CustomerSegment)
        .filter(CustomerSegment.tenant_id == ctx.tenant_id)
        .order_by(CustomerSegment.created_at.desc())
        .all()
    )


def create_segment(db: Session, ctx: TenantContext, data: CustomerSegmentCreate) -> CustomerSegment:
    row = CustomerSegment(
        tenant_id=ctx.tenant_id,
        name=data.name.strip(),
        description=data.description,
        rules=data.rules or {},
        estimated_count=data.estimated_count,
        is_active=data.is_active,
        created_by_user_id=ctx.user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_segment(db: Session, tenant_id: UUID, segment_id: UUID) -> CustomerSegment | None:
    return (
        db.query(CustomerSegment)
        .filter(CustomerSegment.id == segment_id, CustomerSegment.tenant_id == tenant_id)
        .first()
    )


def require_segment(db: Session, ctx: TenantContext, segment_id: UUID) -> CustomerSegment:
    row = get_segment(db, ctx.tenant_id, segment_id)
    if not row:
        raise HTTPException(status_code=404, detail="客户细分不存在")
    return row


def update_segment(
    db: Session, ctx: TenantContext, row: CustomerSegment, data: CustomerSegmentUpdate
) -> CustomerSegment:
    if data.name is not None:
        row.name = data.name.strip()
    if data.description is not None:
        row.description = data.description
    if data.rules is not None:
        row.rules = data.rules
    if data.estimated_count is not None:
        row.estimated_count = data.estimated_count
    if data.is_active is not None:
        row.is_active = data.is_active
    db.commit()
    db.refresh(row)
    return row


def delete_segment(db: Session, row: CustomerSegment) -> None:
    db.delete(row)
    db.commit()
