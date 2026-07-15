"""跟进记录。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import Contract, CrmActivity, Customer, Deal, Lead, Order
from app.permissions import SYSTEM_ROLE_ADMIN
from app.schemas.crm import ActivityCreate, ActivityUpdate, validate_activity_type, validate_lead_status
from app.services.crm.crm_scope_service import (
    assert_can_view_contract,
    assert_can_view_customer,
    assert_can_view_deal,
    assert_can_view_lead,
    assert_can_view_order,
)

_ENTITY_ACTIVITY_TYPES = frozenset({"order", "contract"})


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

    entity_type = (data.entity_type or "").strip().lower() or None
    entity_id = data.entity_id
    if bool(entity_type) != bool(entity_id):
        raise HTTPException(status_code=400, detail="entity_type 与 entity_id 需同时指定")

    fk_linked = sum(1 for x in (data.lead_id, data.customer_id, data.deal_id) if x)
    if entity_type and fk_linked:
        raise HTTPException(status_code=400, detail="实体跟进与 lead/customer/deal 不能同时指定")
    if not entity_type and fk_linked == 0:
        raise HTTPException(status_code=400, detail="必须指定 lead_id、customer_id、deal_id 或 entity_type+entity_id")
    if fk_linked > 1:
        raise HTTPException(status_code=400, detail="lead_id / customer_id / deal_id 只能指定其一")
    if data.status is not None and not data.lead_id:
        raise HTTPException(status_code=400, detail="status 仅可在线索跟进时设置")

    lead: Lead | None = None
    customer: Customer | None = None
    deal: Deal | None = None

    if entity_type:
        if entity_type not in _ENTITY_ACTIVITY_TYPES:
            raise HTTPException(status_code=400, detail="entity_type 仅支持 order / contract")
        if entity_type == "order":
            order = db.query(Order).filter(Order.id == entity_id, Order.tenant_id == ctx.tenant_id).first()
            if not order:
                raise HTTPException(status_code=404, detail="订单不存在")
            assert_can_view_order(ctx, db, order.owner_user_id)
        else:
            contract = (
                db.query(Contract)
                .filter(Contract.id == entity_id, Contract.tenant_id == ctx.tenant_id)
                .first()
            )
            if not contract:
                raise HTTPException(status_code=404, detail="合同不存在")
            assert_can_view_contract(ctx, db, contract.owner_user_id)

        activity = CrmActivity(
            tenant_id=ctx.tenant_id,
            lead_id=None,
            customer_id=None,
            deal_id=None,
            activity_type=data.activity_type,
            subject=data.subject,
            content=data.content or "",
            entity_type=entity_type,
            entity_id=str(entity_id),
            created_by_user_id=ctx.user.id,
        )
        db.add(activity)
        db.commit()
        db.refresh(activity)
        return activity

    if data.lead_id:
        lead = db.query(Lead).filter(Lead.id == data.lead_id, Lead.tenant_id == ctx.tenant_id).first()
        if not lead or lead.deleted_at:
            raise HTTPException(status_code=404, detail="线索不存在")
        assert_can_view_lead(ctx, db, lead.owner_user_id, lead.territory_id)
    elif data.customer_id:
        customer = (
            db.query(Customer)
            .filter(Customer.id == data.customer_id, Customer.tenant_id == ctx.tenant_id)
            .first()
        )
        if not customer or customer.deleted_at:
            raise HTTPException(status_code=404, detail="客户不存在")
        assert_can_view_customer(ctx, db, customer.owner_user_id, customer.territory_id)
    else:
        deal = db.query(Deal).filter(Deal.id == data.deal_id, Deal.tenant_id == ctx.tenant_id).first()
        if not deal:
            raise HTTPException(status_code=404, detail="商机不存在")
        assert_can_view_deal(ctx, db, deal.owner_user_id, deal.territory_id)

    activity = CrmActivity(
        tenant_id=ctx.tenant_id,
        lead_id=data.lead_id,
        customer_id=data.customer_id,
        deal_id=data.deal_id,
        activity_type=data.activity_type,
        subject=data.subject,
        content=data.content or "",
        entity_type=("deal" if deal else "customer" if customer else "lead"),
        entity_id=str((data.deal_id or data.customer_id or data.lead_id)),
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
    deal_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
) -> list[CrmActivity]:
    et = (entity_type or "").strip().lower() or None
    if bool(et) != bool(entity_id):
        raise HTTPException(status_code=400, detail="entity_type 与 entity_id 需同时指定")

    if et:
        if et not in _ENTITY_ACTIVITY_TYPES:
            raise HTTPException(status_code=400, detail="entity_type 仅支持 order / contract")
        if et == "order":
            order = db.query(Order).filter(Order.id == entity_id, Order.tenant_id == ctx.tenant_id).first()
            if not order:
                raise HTTPException(status_code=404, detail="订单不存在")
            assert_can_view_order(ctx, db, order.owner_user_id)
        else:
            contract = (
                db.query(Contract)
                .filter(Contract.id == entity_id, Contract.tenant_id == ctx.tenant_id)
                .first()
            )
            if not contract:
                raise HTTPException(status_code=404, detail="合同不存在")
            assert_can_view_contract(ctx, db, contract.owner_user_id)
        query = db.query(CrmActivity).filter(
            CrmActivity.tenant_id == ctx.tenant_id,
            CrmActivity.entity_type == et,
            CrmActivity.entity_id == str(entity_id),
        )
        return query.order_by(CrmActivity.created_at.desc()).all()

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
    elif deal_id:
        deal = db.query(Deal).filter(Deal.id == deal_id, Deal.tenant_id == ctx.tenant_id).first()
        if not deal:
            raise HTTPException(status_code=404, detail="商机不存在")
        assert_can_view_deal(ctx, db, deal.owner_user_id, deal.territory_id)
        query = db.query(CrmActivity).filter(CrmActivity.deal_id == deal_id)
    else:
        raise HTTPException(status_code=400, detail="必须指定 lead_id、customer_id、deal_id 或 entity_type+entity_id")
    return query.order_by(CrmActivity.created_at.desc()).all()


def update_activity(db: Session, ctx: TenantContext, activity_id: UUID, data: ActivityUpdate) -> CrmActivity:
    activity = db.query(CrmActivity).filter(CrmActivity.id == activity_id, CrmActivity.tenant_id == ctx.tenant_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="跟进记录不存在")
    is_admin = ctx.membership.role.is_system and ctx.membership.role.code == SYSTEM_ROLE_ADMIN
    if activity.created_by_user_id != ctx.user.id and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅作者或管理员可修改")
    if data.activity_type is not None:
        validate_activity_type(data.activity_type)
        activity.activity_type = data.activity_type
    if data.subject is not None:
        activity.subject = data.subject
    if data.content is not None:
        activity.content = data.content
    db.commit()
    db.refresh(activity)
    return activity


def delete_activity(db: Session, ctx: TenantContext, activity_id: UUID) -> None:
    activity = db.query(CrmActivity).filter(CrmActivity.id == activity_id, CrmActivity.tenant_id == ctx.tenant_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="跟进记录不存在")
    is_admin = ctx.membership.role.is_system and ctx.membership.role.code == SYSTEM_ROLE_ADMIN
    if activity.created_by_user_id != ctx.user.id and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅作者或管理员可删除")
    db.delete(activity)
    db.commit()
