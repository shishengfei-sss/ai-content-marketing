"""回款 API（v0.7 CRM-3）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.models.crm import Payment
from app.schemas.crm_deals import (
    PaymentCreate,
    PaymentListResponse,
    PaymentOut,
    PaymentPlanCreate,
    PaymentPlanOut,
    PaymentUpdate,
)
from app.services.crm.crm_scope_service import apply_payment_list_scope, has_payment_list_permission
from app.services.crm.filter_query import parse_list_filters_param
from app.services.crm.payment_service import (
    confirm_payment,
    create_payment,
    create_plan,
    delete_plan,
    require_payment,
    reverse_payment,
    soft_delete_payment,
    update_payment,
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

router = APIRouter(prefix="/payments", tags=["crm-payments"])


@router.get("", response_model=PaymentListResponse)
def list_payments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    view_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    order_id: UUID | None = Query(default=None),
    filters: str | None = Query(default=None, description="高级筛选 JSON"),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None, pattern="^(asc|desc)$"),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.payment.list_own",
            "crm.payment.list_team",
            "crm.payment.list_territory",
            "crm.payment.list_all",
        )
    ),
    db: Session = Depends(get_db),
):
    if not has_payment_list_permission(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")

    active_view = None
    filters_applied = False
    if view_id is not None:
        active_view = get_view(db, ctx.tenant_id, view_id)
        if not active_view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, active_view)

    query = db.query(Payment).filter(Payment.tenant_id == ctx.tenant_id, Payment.deleted_at.is_(None))
    query = apply_payment_list_scope(query, ctx, db)

    if active_view:
        query = apply_view_filters(query, db, ctx.tenant_id, "payment", active_view.filters)
        query = apply_view_search(query, "payment", active_view.search_q)
        query = apply_view_sort(query, "payment", active_view.sort)
    else:
        parsed_filters = parse_list_filters_param(filters)
        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "payment", parsed_filters)
            filters_applied = True
        elif status:
            query = query.filter(Payment.status == status)
        query = apply_view_search(query, "payment", q)
        sort_spec = None
        if sort_by:
            sort_spec = [{"field_key": sort_by, "dir": (sort_dir or "desc").lower()}]
        query = apply_view_sort(query, "payment", sort_spec)

    if order_id is not None:
        query = query.filter(Payment.order_id == order_id)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return PaymentListResponse(
        items=[PaymentOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        list_fields=resolve_view_list_columns(db, ctx.tenant_id, ctx.user.id, "payment", active_view),
        view_id=active_view.id if active_view else None,
        filters_applied=filters_applied if filters else None,
    )


@router.post("", response_model=PaymentOut, status_code=201)
def post_payment(
    body: PaymentCreate,
    ctx: TenantContext = Depends(require_permission("crm.payment.create")),
    db: Session = Depends(get_db),
):
    p = create_payment(db, ctx, body)
    return PaymentOut.model_validate(p)


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment_detail(
    payment_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.payment.view")),
    db: Session = Depends(get_db),
):
    p = require_payment(db, ctx, payment_id)
    return PaymentOut.model_validate(p)


@router.patch("/{payment_id}", response_model=PaymentOut)
def patch_payment(
    payment_id: UUID,
    body: PaymentUpdate,
    ctx: TenantContext = Depends(require_permission("crm.payment.edit")),
    db: Session = Depends(get_db),
):
    p = require_payment(db, ctx, payment_id)
    p = update_payment(db, ctx, p, body)
    return PaymentOut.model_validate(p)


@router.post("/{payment_id}/confirm", response_model=PaymentOut)
def confirm_payment_endpoint(
    payment_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.payment.confirm")),
    db: Session = Depends(get_db),
):
    p = require_payment(db, ctx, payment_id)
    p = confirm_payment(db, ctx, p)
    return PaymentOut.model_validate(p)


@router.post("/{payment_id}/reverse", response_model=PaymentOut)
def reverse_payment_endpoint(
    payment_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.payment.reverse")),
    db: Session = Depends(get_db),
):
    p = require_payment(db, ctx, payment_id)
    p = reverse_payment(db, ctx, p)
    return PaymentOut.model_validate(p)


@router.delete("/{payment_id}", status_code=204)
def delete_payment_endpoint(
    payment_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.payment.delete")),
    db: Session = Depends(get_db),
):
    p = require_payment(db, ctx, payment_id)
    soft_delete_payment(db, p)


# ---------------- 回款计划 ----------------


@router.get("/orders/{order_id}/plans", response_model=list[PaymentPlanOut])
def list_order_plans(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.payment.view")),
    db: Session = Depends(get_db),
):
    from app.services.crm.order_service import require_order

    require_order(db, ctx, order_id)
    from app.services.crm.payment_service import list_plans_for_order

    plans = list_plans_for_order(db, ctx.tenant_id, order_id)
    return [PaymentPlanOut.model_validate(p) for p in plans]


@router.post("/orders/{order_id}/plans", response_model=PaymentPlanOut, status_code=201)
def create_order_plan(
    order_id: UUID,
    body: PaymentPlanCreate,
    ctx: TenantContext = Depends(require_permission("crm.payment.create")),
    db: Session = Depends(get_db),
):
    plan = create_plan(db, ctx, order_id, body)
    return PaymentPlanOut.model_validate(plan)


@router.delete("/plans/{plan_id}", status_code=204)
def delete_order_plan(
    plan_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.payment.delete")),
    db: Session = Depends(get_db),
):
    delete_plan(db, ctx, plan_id)
