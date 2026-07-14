"""线索 CRUD。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Contact, CrmActivity, Customer, Lead
from app.schemas.crm import LeadCreate, LeadUpdate, validate_lead_mobile_value, validate_lead_status
from app.services.crm.crm_scope_service import assert_can_view_lead, can_view_customer
from app.services.crm.number_service import generate_number
from app.services.crm.sales_org_service import get_territory
from app.services.crm.schema_service import validate_extra_data


def _perm_set(ctx: TenantContext) -> set[str]:
    return {p.permission_code for p in ctx.membership.role.permissions}


def get_lead(db: Session, tenant_id: UUID, lead_id: UUID) -> Lead | None:
    return (
        db.query(Lead)
        .filter(
            uuid_eq(Lead.id, lead_id),
            Lead.tenant_id == tenant_id,
            Lead.deleted_at.is_(None),
        )
        .first()
    )


def create_lead(db: Session, ctx: TenantContext, data: LeadCreate) -> Lead:
    validate_lead_status(data.status)
    mobile, mobile_err = validate_lead_mobile_value(data.mobile, required=True)
    if mobile_err:
        raise HTTPException(status_code=422, detail=mobile_err)
    extra = validate_extra_data(db, ctx.tenant_id, "lead", data.extra_data, is_create=True)
    if data.territory_id is not None and not get_territory(db, ctx.tenant_id, data.territory_id):
        raise HTTPException(status_code=404, detail="地区不存在")
    lead = Lead(
        tenant_id=ctx.tenant_id,
        lead_number=generate_number(db, ctx.tenant_id, "lead"),
        company_name=data.company_name.strip(),
        contact_name=data.contact_name,
        mobile=mobile,
        phone=data.phone,
        email=data.email,
        source=data.source,
        status=data.status,
        owner_user_id=ctx.user.id,
        territory_id=data.territory_id,
        remark=data.remark,
        extra_data=extra,
        campaign_id=data.campaign_id,
        created_by_user_id=ctx.user.id,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def update_lead(db: Session, ctx: TenantContext, lead: Lead, data: LeadUpdate) -> Lead:
    perms = _perm_set(ctx)
    if data.owner_user_id is not None and data.owner_user_id != lead.owner_user_id:
        if "crm.lead.assign" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        lead.owner_user_id = data.owner_user_id
    if data.company_name is not None:
        lead.company_name = data.company_name.strip()
    if data.contact_name is not None:
        lead.contact_name = data.contact_name
    if data.mobile is not None:
        mobile, mobile_err = validate_lead_mobile_value(data.mobile, required=True)
        if mobile_err:
            raise HTTPException(status_code=422, detail=mobile_err)
        lead.mobile = mobile
    if data.phone is not None:
        lead.phone = data.phone
    if data.email is not None:
        lead.email = data.email
    if data.source is not None:
        lead.source = data.source
    if data.status is not None:
        validate_lead_status(data.status)
        lead.status = data.status
    if data.remark is not None:
        lead.remark = data.remark
    if data.extra_data is not None:
        merged = dict(lead.extra_data or {})
        merged.update(data.extra_data)
        lead.extra_data = validate_extra_data(db, ctx.tenant_id, "lead", merged)
    if "campaign_id" in data.model_fields_set:
        lead.campaign_id = data.campaign_id
    if data.territory_id is not None:
        if not get_territory(db, ctx.tenant_id, data.territory_id):
            raise HTTPException(status_code=404, detail="地区不存在")
        lead.territory_id = data.territory_id
    db.commit()
    db.refresh(lead)
    return lead


def soft_delete_lead(db: Session, lead: Lead) -> None:
    lead.deleted_at = datetime.now(timezone.utc)
    db.commit()


def require_lead(db: Session, ctx: TenantContext, lead_id: UUID) -> Lead:
    lead = get_lead(db, ctx.tenant_id, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    assert_can_view_lead(ctx, db, lead.owner_user_id, lead.territory_id)
    return lead


def convert_lead_to_customer(db: Session, ctx: TenantContext, lead: Lead) -> tuple[Customer, Contact | None]:
    if lead.status == "已转化" or lead.converted_customer_id:
        raise HTTPException(status_code=409, detail="线索已转化")
    customer = Customer(
        tenant_id=ctx.tenant_id,
        company_name=lead.company_name,
        mobile=lead.mobile,
        phone=lead.phone,
        email=lead.email,
        status="潜在",
        owner_user_id=lead.owner_user_id,
        territory_id=lead.territory_id,
        campaign_id=lead.campaign_id,
        converted_from_lead_id=lead.id,
        remark=lead.remark,
        extra_data=dict(lead.extra_data or {}),
        created_by_user_id=ctx.user.id,
    )
    db.add(customer)
    db.flush()
    contact = None
    if lead.contact_name:
        contact = Contact(
            tenant_id=ctx.tenant_id,
            customer_id=customer.id,
            name=lead.contact_name,
            mobile=lead.mobile,
            phone=lead.phone,
            email=lead.email,
            is_primary=True,
            extra_data=dict(lead.extra_data or {}),
        )
        db.add(contact)
    lead.status = "已转化"
    lead.converted_customer_id = customer.id
    if not can_view_customer(ctx, db, customer.owner_user_id, customer.territory_id):
        customer.owner_user_id = ctx.user.id
    _copy_lead_activities_to_customer(db, ctx, lead, customer)
    db.commit()
    db.refresh(customer)
    if contact:
        db.refresh(contact)
    db.refresh(lead)
    return customer, contact


def _copy_lead_activities_to_customer(db: Session, ctx: TenantContext, lead: Lead, customer: Customer) -> None:
    activities = db.query(CrmActivity).filter(CrmActivity.lead_id == lead.id).order_by(CrmActivity.created_at).all()
    for act in activities:
        db.add(
            CrmActivity(
                tenant_id=ctx.tenant_id,
                customer_id=customer.id,
                activity_type=act.activity_type,
                content=act.content,
                created_by_user_id=act.created_by_user_id,
            )
        )
    db.flush()
