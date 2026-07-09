"""跟进记录。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import CrmActivity, Customer, Lead
from app.schemas.crm import ActivityCreate, validate_activity_type, validate_lead_status
from app.services.crm.crm_scope_service import assert_can_view_customer, assert_can_view_lead


def _write_follow_up_meta(
    entity: Lead | Customer,
    *,
    content: str,
    next_follow_up_at: datetime | None,
) -> None:
    now = datetime.now(timezone.utc)
    extra = dict(entity.extra_data or {})
    extra["last_follow_up_at"] = now.isoformat()
    extra["last_follow_up_content"] = (content or "")[:500]
    entity.extra_data = extra
    if next_follow_up_at is not None:
        entity.next_follow_up_at = next_follow_up_at


def _role_permissions(ctx: TenantContext) -> set[str]:
    return {p.permission_code for p in ctx.membership.role.permissions}


def create_activity(db: Session, ctx: TenantContext, data: ActivityCreate) -> CrmActivity:
    validate_activity_type(data.activity_type)
    if not data.lead_id and not data.customer_id:
        raise HTTPException(status_code=400, detail="必须指定 lead_id 或 customer_id")
    if data.lead_id and data.customer_id:
        raise HTTPException(status_code=400, detail="不能同时指定 lead_id 与 customer_id")
    if data.status is not None and not data.lead_id:
        raise HTTPException(status_code=400, detail="status 仅可在线索跟进时设置")

    lead: Lead | None = None
    customer: Customer | None = None

    if data.lead_id:
        lead = db.query(Lead).filter(Lead.id == data.lead_id, Lead.tenant_id == ctx.tenant_id).first()
        if not lead or lead.deleted_at:
            raise HTTPException(status_code=404, detail="线索不存在")
        assert_can_view_lead(ctx, db, lead.owner_user_id, lead.territory_id)
    else:
        customer = (
            db.query(Customer)
            .filter(Customer.id == data.customer_id, Customer.tenant_id == ctx.tenant_id)
            .first()
        )
        if not customer or customer.deleted_at:
            raise HTTPException(status_code=404, detail="客户不存在")
        assert_can_view_customer(ctx, db, customer.owner_user_id, customer.territory_id)

    activity = CrmActivity(
        tenant_id=ctx.tenant_id,
        lead_id=data.lead_id,
        customer_id=data.customer_id,
        activity_type=data.activity_type,
        content=data.content or "",
        created_by_user_id=ctx.user.id,
    )
    db.add(activity)

    if lead:
        _write_follow_up_meta(lead, content=data.content or "", next_follow_up_at=data.next_follow_up_at)
        if data.status is not None:
            status_val = str(data.status).strip()
            if status_val and status_val != (lead.status or ""):
                if "crm.lead.edit" not in _role_permissions(ctx):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改线索状态")
                try:
                    validate_lead_status(status_val)
                except ValueError as e:
                    raise HTTPException(status_code=422, detail=str(e)) from e
                lead.status = status_val
    elif customer:
        _write_follow_up_meta(customer, content=data.content or "", next_follow_up_at=data.next_follow_up_at)

    db.commit()
    db.refresh(activity)
    return activity


def list_activities(
    db: Session,
    ctx: TenantContext,
    *,
    lead_id: UUID | None = None,
    customer_id: UUID | None = None,
) -> list[CrmActivity]:
    if lead_id:
        lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == ctx.tenant_id).first()
        if not lead or lead.deleted_at:
            raise HTTPException(status_code=404, detail="线索不存在")
        assert_can_view_lead(ctx, db, lead.owner_user_id, lead.territory_id)
        query = db.query(CrmActivity).filter(CrmActivity.lead_id == lead_id)
    elif customer_id:
        customer = (
            db.query(Customer)
            .filter(Customer.id == customer_id, Customer.tenant_id == ctx.tenant_id)
            .first()
        )
        if not customer or customer.deleted_at:
            raise HTTPException(status_code=404, detail="客户不存在")
        assert_can_view_customer(ctx, db, customer.owner_user_id, customer.territory_id)
        query = db.query(CrmActivity).filter(CrmActivity.customer_id == customer_id)
    else:
        raise HTTPException(status_code=400, detail="必须指定 lead_id 或 customer_id")
    return query.order_by(CrmActivity.created_at.desc()).all()


def delete_activity(db: Session, ctx: TenantContext, activity_id: UUID) -> None:
    from app.permissions import SYSTEM_ROLE_ADMIN

    activity = db.query(CrmActivity).filter(CrmActivity.id == activity_id, CrmActivity.tenant_id == ctx.tenant_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="跟进记录不存在")

    if activity.lead_id:
        lead = db.query(Lead).filter(Lead.id == activity.lead_id, Lead.tenant_id == ctx.tenant_id).first()
        if lead and not lead.deleted_at:
            assert_can_view_lead(ctx, db, lead.owner_user_id, lead.territory_id)
    elif activity.customer_id:
        customer = (
            db.query(Customer)
            .filter(Customer.id == activity.customer_id, Customer.tenant_id == ctx.tenant_id)
            .first()
        )
        if customer and not customer.deleted_at:
            assert_can_view_customer(ctx, db, customer.owner_user_id, customer.territory_id)

    is_admin = ctx.membership.role.is_system and ctx.membership.role.code == SYSTEM_ROLE_ADMIN
    if activity.created_by_user_id != ctx.user.id and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该跟进")

    db.delete(activity)
    db.commit()
