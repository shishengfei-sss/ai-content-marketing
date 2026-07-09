"""客户与联系人 API。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.models.crm import Customer
from app.schemas.crm import (
    ContactCreate,
    ContactOut,
    CustomerCreate,
    CustomerListResponse,
    CustomerOut,
    CustomerUpdate,
)
from app.services.crm.crm_scope_service import apply_customer_list_scope, has_customer_list_permission
from app.services.crm.customer_service import (
    create_contact,
    create_customer,
    list_contacts,
    require_customer,
    soft_delete_customer,
    update_customer,
)
from app.services.crm.view_service import (
    apply_view_filters,
    apply_view_search,
    apply_view_sort,
    assert_can_access_view,
    get_view,
    resolve_view_list_columns,
)
from app.services.crm.filter_query import parse_list_filters_param
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/customers", tags=["crm-customers"])


@router.get("", response_model=CustomerListResponse)
def list_customers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    view_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    filters: str | None = Query(default=None, description="高级筛选 JSON"),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.customer.list_own",
            "crm.customer.list_team",
            "crm.customer.list_territory",
            "crm.customer.list_all",
        )
    ),
    db: Session = Depends(get_db),
):
    if not has_customer_list_permission(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")

    active_view = None
    if view_id is not None:
        active_view = get_view(db, ctx.tenant_id, view_id)
        if not active_view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, active_view)

    query = db.query(Customer).filter(Customer.tenant_id == ctx.tenant_id, Customer.deleted_at.is_(None))
    query = apply_customer_list_scope(query, ctx, db)

    if active_view:
        query = apply_view_filters(query, db, ctx.tenant_id, "customer", active_view.filters)
        query = apply_view_search(query, "customer", active_view.search_q)
        query = apply_view_sort(query, "customer", active_view.sort)
    else:
        parsed_filters = parse_list_filters_param(filters)
        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "customer", parsed_filters)
        elif status:
            query = query.filter(Customer.status == status)
        query = apply_view_search(query, "customer", q)
        query = apply_view_sort(query, "customer", None)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return CustomerListResponse(
        items=[CustomerOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        list_fields=resolve_view_list_columns(db, ctx.tenant_id, ctx.user.id, "customer", active_view),
        view_id=active_view.id if active_view else None,
    )


@router.post("", response_model=CustomerOut, status_code=201)
def post_customer(
    body: CustomerCreate,
    ctx: TenantContext = Depends(require_permission("crm.customer.create")),
    db: Session = Depends(get_db),
):
    customer = create_customer(db, ctx, body)
    return CustomerOut.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer_detail(
    customer_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.customer.view")),
    db: Session = Depends(get_db),
):
    customer = require_customer(db, ctx, customer_id)
    return CustomerOut.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerOut)
def patch_customer(
    customer_id: UUID,
    body: CustomerUpdate,
    ctx: TenantContext = Depends(require_permission("crm.customer.edit")),
    db: Session = Depends(get_db),
):
    customer = require_customer(db, ctx, customer_id)
    customer = update_customer(db, ctx, customer, body)
    return CustomerOut.model_validate(customer)


@router.delete("/{customer_id}", status_code=204)
def delete_customer(
    customer_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.customer.delete")),
    db: Session = Depends(get_db),
):
    customer = require_customer(db, ctx, customer_id)
    soft_delete_customer(db, customer)


@router.get("/{customer_id}/contacts", response_model=list[ContactOut])
def get_contacts(
    customer_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.customer.view")),
    db: Session = Depends(get_db),
):
    customer = require_customer(db, ctx, customer_id)
    return [ContactOut.model_validate(c) for c in list_contacts(db, customer.id)]


@router.post("/{customer_id}/contacts", response_model=ContactOut, status_code=201)
def post_contact(
    customer_id: UUID,
    body: ContactCreate,
    ctx: TenantContext = Depends(require_permission("crm.customer.edit")),
    db: Session = Depends(get_db),
):
    customer = require_customer(db, ctx, customer_id)
    contact = create_contact(db, ctx, customer, body)
    return ContactOut.model_validate(contact)
