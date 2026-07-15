"""订单 API（v0.7 CRM-2/3）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.models.crm import Order
from app.schemas.crm_deals import (
    ApprovalInstanceOut,
    DeliveryCreate,
    DeliveryOut,
    InvoiceCreate,
    InvoiceOut,
    OrderCreate,
    OrderListResponse,
    OrderOut,
    OrderRejectBody,
    OrderReviseBody,
    OrderUpdate,
)
from app.services.crm.crm_scope_service import apply_order_list_scope, has_order_list_permission
from app.services.crm.delivery_service import create_delivery, list_order_deliveries
from app.services.crm.filter_query import parse_list_filters_param
from app.services.crm.invoice_service import create_invoice, list_order_invoices
from app.services.crm.order_service import (
    approve_order,
    cancel_order,
    confirm_order,
    create_order,
    list_order_approvals,
    list_order_revisions,
    reject_order,
    require_order,
    revise_order,
    soft_delete_order,
    submit_order,
    update_order,
)
from app.services.crm.view_service import (
    apply_view_filters,
    apply_view_search,
    apply_view_sort,
    assert_can_access_view,
    get_view,
    resolve_view_list_columns,
)
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/orders", tags=["crm-orders"])


@router.get("", response_model=OrderListResponse)
def list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    view_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),
    deal_id: UUID | None = Query(default=None),
    contract_id: UUID | None = Query(default=None),
    filters: str | None = Query(default=None, description="高级筛选 JSON"),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None, pattern="^(asc|desc)$"),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.order.list_own",
            "crm.order.list_team",
            "crm.order.list_territory",
            "crm.order.list_all",
        )
    ),
    db: Session = Depends(get_db),
):
    if not has_order_list_permission(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")

    active_view = None
    filters_applied = False
    if view_id is not None:
        active_view = get_view(db, ctx.tenant_id, view_id)
        if not active_view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, active_view)

    query = db.query(Order).filter(Order.tenant_id == ctx.tenant_id, Order.deleted_at.is_(None))
    query = apply_order_list_scope(query, ctx, db)

    if active_view:
        query = apply_view_filters(query, db, ctx.tenant_id, "order", active_view.filters)
        query = apply_view_search(query, "order", active_view.search_q)
        query = apply_view_sort(query, "order", active_view.sort)
    else:
        parsed_filters = parse_list_filters_param(filters)
        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "order", parsed_filters)
            filters_applied = True
        elif status:
            query = query.filter(Order.status == status)
        query = apply_view_search(query, "order", q)
        sort_spec = None
        if sort_by:
            sort_spec = [{"field_key": sort_by, "dir": (sort_dir or "desc").lower()}]
        query = apply_view_sort(query, "order", sort_spec)

    if customer_id is not None:
        query = query.filter(Order.customer_id == customer_id)
    if deal_id is not None:
        query = query.filter(Order.deal_id == deal_id)
    if contract_id is not None:
        query = query.filter(Order.contract_id == contract_id)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return OrderListResponse(
        items=[OrderOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        list_fields=resolve_view_list_columns(db, ctx.tenant_id, ctx.user.id, "order", active_view),
        view_id=active_view.id if active_view else None,
        filters_applied=filters_applied if filters else None,
    )


@router.post("", response_model=OrderOut, status_code=201)
def post_order(
    body: OrderCreate,
    ctx: TenantContext = Depends(require_permission("crm.order.create")),
    db: Session = Depends(get_db),
):
    o = create_order(db, ctx, body)
    return OrderOut.model_validate(o)


@router.get("/{order_id}", response_model=OrderOut)
def get_order_detail(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.view")),
    db: Session = Depends(get_db),
):
    o = require_order(db, ctx, order_id)
    return OrderOut.model_validate(o)


@router.patch("/{order_id}", response_model=OrderOut)
def patch_order(
    order_id: UUID,
    body: OrderUpdate,
    ctx: TenantContext = Depends(require_permission("crm.order.edit")),
    db: Session = Depends(get_db),
):
    o = require_order(db, ctx, order_id)
    o = update_order(db, ctx, o, body)
    return OrderOut.model_validate(o)


@router.post("/{order_id}/confirm", response_model=OrderOut)
def confirm_order_endpoint(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.place")),
    db: Session = Depends(get_db),
):
    o = require_order(db, ctx, order_id)
    o = confirm_order(db, ctx, o)
    return OrderOut.model_validate(o)


@router.post("/{order_id}/submit", response_model=OrderOut)
def submit_order_endpoint(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.place")),
    db: Session = Depends(get_db),
):
    o = require_order(db, ctx, order_id)
    o = submit_order(db, ctx, o)
    return OrderOut.model_validate(o)


@router.post("/{order_id}/approve", response_model=OrderOut)
def approve_order_endpoint(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.approve")),
    db: Session = Depends(get_db),
):
    o = require_order(db, ctx, order_id)
    o = approve_order(db, ctx, o)
    return OrderOut.model_validate(o)


@router.post("/{order_id}/reject", response_model=OrderOut)
def reject_order_endpoint(
    order_id: UUID,
    body: OrderRejectBody,
    ctx: TenantContext = Depends(require_permission("crm.order.approve")),
    db: Session = Depends(get_db),
):
    o = require_order(db, ctx, order_id)
    o = reject_order(db, ctx, o, body.reason)
    return OrderOut.model_validate(o)


@router.get("/{order_id}/approvals", response_model=list[ApprovalInstanceOut])
def list_order_approvals_endpoint(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.view")),
    db: Session = Depends(get_db),
):
    require_order(db, ctx, order_id)
    items = list_order_approvals(db, ctx.tenant_id, order_id)
    return [ApprovalInstanceOut.model_validate(i) for i in items]


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order_endpoint(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.edit")),
    db: Session = Depends(get_db),
):
    o = require_order(db, ctx, order_id)
    o = cancel_order(db, ctx, o)
    return OrderOut.model_validate(o)


@router.post("/{order_id}/revise", response_model=OrderOut, status_code=201)
def revise_order_endpoint(
    order_id: UUID,
    body: OrderReviseBody,
    ctx: TenantContext = Depends(require_permission("crm.order.place")),
    db: Session = Depends(get_db),
):
    o = require_order(db, ctx, order_id)
    revised = revise_order(db, ctx, o, reason=body.reason, lines=body.lines, title=body.title)
    return OrderOut.model_validate(revised)


@router.get("/{order_id}/revisions", response_model=list[OrderOut])
def list_order_revisions_endpoint(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.view")),
    db: Session = Depends(get_db),
):
    items = list_order_revisions(db, ctx, order_id)
    return [OrderOut.model_validate(i) for i in items]


@router.get("/{order_id}/deliveries", response_model=list[DeliveryOut])
def list_order_deliveries_endpoint(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.view")),
    db: Session = Depends(get_db),
):
    items = list_order_deliveries(db, ctx, order_id)
    return [DeliveryOut.model_validate(i) for i in items]


@router.post("/{order_id}/deliveries", response_model=DeliveryOut, status_code=201)
def create_order_delivery_endpoint(
    order_id: UUID,
    body: DeliveryCreate,
    ctx: TenantContext = Depends(require_permission("crm.order.edit")),
    db: Session = Depends(get_db),
):
    note = create_delivery(db, ctx, order_id, body)
    return DeliveryOut.model_validate(note)


@router.get("/{order_id}/invoices", response_model=list[InvoiceOut])
def list_order_invoices_endpoint(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.view")),
    db: Session = Depends(get_db),
):
    items = list_order_invoices(db, ctx, order_id)
    return [InvoiceOut.model_validate(i) for i in items]


@router.post("/{order_id}/invoices", response_model=InvoiceOut, status_code=201)
def create_order_invoice_endpoint(
    order_id: UUID,
    body: InvoiceCreate,
    ctx: TenantContext = Depends(require_permission("crm.order.edit")),
    db: Session = Depends(get_db),
):
    inv = create_invoice(db, ctx, order_id, body)
    return InvoiceOut.model_validate(inv)


@router.delete("/{order_id}", status_code=204)
def delete_order_endpoint(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.delete")),
    db: Session = Depends(get_db),
):
    o = require_order(db, ctx, order_id)
    soft_delete_order(db, o)
