"""客户与联系人 CRUD。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Contact, Customer
from app.schemas.crm import ContactCreate, CustomerCreate, CustomerUpdate, validate_customer_status
from app.services.crm.crm_scope_service import assert_can_view_customer
from app.services.crm.schema_service import validate_extra_data


def _perm_set(ctx: TenantContext) -> set[str]:
    return {p.permission_code for p in ctx.membership.role.permissions}


def get_customer(db: Session, tenant_id: UUID, customer_id: UUID) -> Customer | None:
    return (
        db.query(Customer)
        .filter(
            uuid_eq(Customer.id, customer_id),
            Customer.tenant_id == tenant_id,
            Customer.deleted_at.is_(None),
        )
        .first()
    )


def create_customer(db: Session, ctx: TenantContext, data: CustomerCreate) -> Customer:
    validate_customer_status(data.status)
    extra = validate_extra_data(db, ctx.tenant_id, "customer", data.extra_data, is_create=True)
    customer = Customer(
        tenant_id=ctx.tenant_id,
        company_name=data.company_name.strip(),
        mobile=data.mobile,
        phone=data.phone,
        email=data.email,
        status=data.status,
        owner_user_id=ctx.user.id,
        remark=data.remark,
        extra_data=extra,
        created_by_user_id=ctx.user.id,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def update_customer(db: Session, ctx: TenantContext, customer: Customer, data: CustomerUpdate) -> Customer:
    perms = _perm_set(ctx)
    if data.owner_user_id is not None and data.owner_user_id != customer.owner_user_id:
        if "crm.customer.assign" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        customer.owner_user_id = data.owner_user_id
    if data.company_name is not None:
        customer.company_name = data.company_name.strip()
    if data.mobile is not None:
        customer.mobile = data.mobile
    if data.phone is not None:
        customer.phone = data.phone
    if data.email is not None:
        customer.email = data.email
    if data.status is not None:
        validate_customer_status(data.status)
        customer.status = data.status
    if data.remark is not None:
        customer.remark = data.remark
    if data.extra_data is not None:
        merged = dict(customer.extra_data or {})
        merged.update(data.extra_data)
        customer.extra_data = validate_extra_data(db, ctx.tenant_id, "customer", merged)
    db.commit()
    db.refresh(customer)
    return customer


def soft_delete_customer(db: Session, customer: Customer) -> None:
    customer.deleted_at = datetime.now(timezone.utc)
    db.commit()


def require_customer(db: Session, ctx: TenantContext, customer_id: UUID) -> Customer:
    customer = get_customer(db, ctx.tenant_id, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    assert_can_view_customer(ctx, db, customer.owner_user_id, customer.territory_id)
    return customer


def create_contact(db: Session, ctx: TenantContext, customer: Customer, data: ContactCreate) -> Contact:
    if data.is_primary:
        db.query(Contact).filter(
            Contact.customer_id == customer.id,
            Contact.deleted_at.is_(None),
            Contact.is_primary.is_(True),
        ).update({Contact.is_primary: False})
    contact = Contact(
        tenant_id=ctx.tenant_id,
        customer_id=customer.id,
        name=data.name.strip(),
        mobile=data.mobile,
        phone=data.phone,
        email=data.email,
        wechat=data.wechat,
        title=data.title,
        department=data.department,
        is_primary=data.is_primary,
        is_decision_maker=data.is_decision_maker,
        remark=data.remark,
        extra_data=data.extra_data or {},
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def list_contacts(db: Session, customer_id: UUID) -> list[Contact]:
    return (
        db.query(Contact)
        .filter(Contact.customer_id == customer_id, Contact.deleted_at.is_(None))
        .order_by(Contact.is_primary.desc(), Contact.created_at.asc())
        .all()
    )
