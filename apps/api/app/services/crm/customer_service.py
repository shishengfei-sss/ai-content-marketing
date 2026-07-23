"""客户与联系人 CRUD。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Contact, Customer
from app.schemas.crm import (
    ContactCreate,
    ContactUpdate,
    CustomerCreate,
    CustomerUpdate,
    validate_customer_status,
)
from app.services.crm.crm_scope_service import assert_can_mutate_customer, assert_can_view_customer
from app.services.crm.number_service import generate_number
from app.services.crm.sales_org_service import (
    apply_creator_org_defaults,
    apply_owner_org_snapshot,
    assert_can_assign_owner,
    get_territory,
)
from app.services.crm.schema_service import validate_extra_data
from app.services.membership_service import get_membership_permissions


def _perm_set(ctx: TenantContext) -> set[str]:
    return set(get_membership_permissions(ctx.membership))


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
    from app.services.text_sanitize import sanitize_plain_text

    validate_customer_status(data.status)
    company_name = sanitize_plain_text(data.company_name) or ""
    if not company_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="公司名称不能为空")
    dup = (
        db.query(Customer)
        .filter(
            Customer.tenant_id == ctx.tenant_id,
            Customer.company_name == company_name,
            Customer.deleted_at.is_(None),
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="客户名称已存在")
    extra = validate_extra_data(db, ctx.tenant_id, "customer", data.extra_data, is_create=True)
    territory_id, manager_user_id = apply_creator_org_defaults(
        db, ctx, territory_id=getattr(data, "territory_id", None)
    )
    customer = Customer(
        tenant_id=ctx.tenant_id,
        customer_number=generate_number(db, ctx.tenant_id, "customer"),
        company_name=company_name,
        mobile=data.mobile,
        phone=data.phone,
        email=data.email,
        status=data.status,
        description=data.description,
        type=data.type or "客户",
        parent_customer_id=data.parent_customer_id,
        tags=list(data.tags or []),
        source=data.source,
        owner_user_id=ctx.user.id,
        territory_id=territory_id,
        manager_user_id=manager_user_id,
        remark=data.remark,
        extra_data=extra,
        created_by_user_id=ctx.user.id,
    )
    db.add(customer)
    db.flush()
    if data.tags:
        from app.services.crm.tag_service import sync_customer_tag_names

        sync_customer_tag_names(db, ctx, customer, list(data.tags))
    else:
        db.commit()
    db.refresh(customer)
    return customer


def update_customer(db: Session, ctx: TenantContext, customer: Customer, data: CustomerUpdate) -> Customer:
    perms = _perm_set(ctx)
    changing_owner = data.owner_user_id is not None and data.owner_user_id != customer.owner_user_id
    # 除分配负责人外，其它字段变更仅负责人可操作
    mutate_keys = set(data.model_fields_set) - {"owner_user_id"}
    if mutate_keys:
        assert_can_mutate_customer(ctx, customer)

    if changing_owner:
        if "crm.customer.assign" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        assert_can_assign_owner(db, ctx, data.owner_user_id)
        customer.owner_user_id = data.owner_user_id
        # 跟随新负责人落地区/汇报上级，避免原负责人因地区/上级快照仍可见
        snap_territory, snap_manager = apply_owner_org_snapshot(db, ctx.tenant_id, data.owner_user_id)
        if data.territory_id is None:
            customer.territory_id = snap_territory
        customer.manager_user_id = snap_manager
        if getattr(customer, "pool_id", None) is not None:
            customer.pool_id = None
            customer.claimed_at = None
    if data.territory_id is not None:
        if not get_territory(db, ctx.tenant_id, data.territory_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="销售区域不存在")
        customer.territory_id = data.territory_id
    if data.company_name is not None:
        from app.services.text_sanitize import sanitize_plain_text

        new_name = sanitize_plain_text(data.company_name) or ""
        if not new_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="公司名称不能为空")
        if new_name != customer.company_name:
            dup = (
                db.query(Customer)
                .filter(
                    Customer.tenant_id == ctx.tenant_id,
                    Customer.company_name == new_name,
                    Customer.deleted_at.is_(None),
                    Customer.id != customer.id,
                )
                .first()
            )
            if dup:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="客户名称已存在")
        customer.company_name = new_name
    if data.mobile is not None:
        customer.mobile = data.mobile
    if data.phone is not None:
        customer.phone = data.phone
    if data.email is not None:
        customer.email = data.email
    if data.status is not None:
        validate_customer_status(data.status)
        customer.status = data.status
    if data.description is not None:
        customer.description = data.description
    if data.type is not None:
        customer.type = data.type
    if "parent_customer_id" in data.model_fields_set:
        customer.parent_customer_id = data.parent_customer_id
    if data.tags is not None:
        customer.tags = list(data.tags)
    if data.source is not None:
        customer.source = data.source
    if data.remark is not None:
        customer.remark = data.remark
    if data.extra_data is not None:
        merged = dict(customer.extra_data or {})
        merged.update(data.extra_data)
        customer.extra_data = validate_extra_data(db, ctx.tenant_id, "customer", merged)
    db.commit()
    db.refresh(customer)
    return customer


def soft_delete_customer(db: Session, ctx: TenantContext, customer: Customer) -> None:
    assert_can_mutate_customer(ctx, customer)
    customer.deleted_at = datetime.now(timezone.utc)
    db.commit()


def require_customer(db: Session, ctx: TenantContext, customer_id: UUID) -> Customer:
    customer = get_customer(db, ctx.tenant_id, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    assert_can_view_customer(
        ctx,
        db,
        customer.owner_user_id,
        customer.territory_id,
        created_by_user_id=customer.created_by_user_id,
        manager_user_id=getattr(customer, "manager_user_id", None),
        pool_id=getattr(customer, "pool_id", None),
    )
    return customer


def create_contact(db: Session, ctx: TenantContext, customer: Customer, data: ContactCreate) -> Contact:
    assert_can_mutate_customer(ctx, customer)
    if data.is_primary:
        db.query(Contact).filter(
            Contact.customer_id == customer.id,
            Contact.deleted_at.is_(None),
            Contact.is_primary.is_(True),
        ).update({Contact.is_primary: False})
    reports_to = None
    if data.reports_to_contact_id is not None:
        reports_to = (
            db.query(Contact)
            .filter(
                uuid_eq(Contact.id, data.reports_to_contact_id),
                Contact.tenant_id == ctx.tenant_id,
                uuid_eq(Contact.customer_id, customer.id),
                Contact.deleted_at.is_(None),
            )
            .first()
        )
        if not reports_to:
            raise HTTPException(status_code=400, detail="汇报对象必须是同客户下的联系人")
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
        contact_role=data.contact_role,
        reports_to_contact_id=reports_to.id if reports_to else None,
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


def get_contact(db: Session, tenant_id: UUID, customer_id: UUID, contact_id: UUID) -> Contact | None:
    return (
        db.query(Contact)
        .filter(
            uuid_eq(Contact.id, contact_id),
            Contact.tenant_id == tenant_id,
            uuid_eq(Contact.customer_id, customer_id),
            Contact.deleted_at.is_(None),
        )
        .first()
    )


def update_contact(
    db: Session, ctx: TenantContext, customer: Customer, contact: Contact, data: ContactUpdate
) -> Contact:
    assert_can_mutate_customer(ctx, customer)
    if data.is_primary is True:
        db.query(Contact).filter(
            Contact.customer_id == customer.id,
            Contact.deleted_at.is_(None),
            Contact.is_primary.is_(True),
            Contact.id != contact.id,
        ).update({Contact.is_primary: False})
    if data.reports_to_contact_id is not None:
        if data.reports_to_contact_id == contact.id:
            raise HTTPException(status_code=400, detail="不能将自己设为汇报对象")
        reports_to = get_contact(db, ctx.tenant_id, customer.id, data.reports_to_contact_id)
        if not reports_to:
            raise HTTPException(status_code=400, detail="汇报对象必须是同客户下的联系人")
        contact.reports_to_contact_id = reports_to.id
    payload = data.model_dump(exclude_unset=True, exclude={"reports_to_contact_id"})
    for key, value in payload.items():
        if key == "name" and value is not None:
            setattr(contact, key, value.strip())
        else:
            setattr(contact, key, value)
    db.commit()
    db.refresh(contact)
    return contact


def soft_delete_contact(db: Session, ctx: TenantContext, customer: Customer, contact: Contact) -> None:
    assert_can_mutate_customer(ctx, customer)
    contact.deleted_at = datetime.now(timezone.utc)
    db.commit()
