"""报价 API（v0.7 CRM-2）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.models.crm import Quote
from app.schemas.crm_deals import (
    QuoteConvertToOrderOut,
    QuoteCreate,
    QuoteListResponse,
    QuoteOut,
    QuoteUpdate,
)
from app.services.crm.crm_scope_service import apply_quote_list_scope, has_quote_list_permission
from app.services.crm.filter_query import parse_list_filters_param
from app.services.crm.quote_service import (
    accept_quote,
    convert_quote_to_order,
    create_quote,
    require_quote,
    send_quote,
    soft_delete_quote,
    update_quote,
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

router = APIRouter(prefix="/quotes", tags=["crm-quotes"])


@router.get("", response_model=QuoteListResponse)
def list_quotes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    view_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),
    deal_id: UUID | None = Query(default=None),
    filters: str | None = Query(default=None, description="高级筛选 JSON"),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None, pattern="^(asc|desc)$"),
    ctx: TenantContext = Depends(
        require_any_permission("crm.quote.list_own", "crm.quote.list_all")
    ),
    db: Session = Depends(get_db),
):
    if not has_quote_list_permission(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")

    active_view = None
    filters_applied = False
    if view_id is not None:
        active_view = get_view(db, ctx.tenant_id, view_id)
        if not active_view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, active_view)

    query = db.query(Quote).filter(Quote.tenant_id == ctx.tenant_id, Quote.deleted_at.is_(None))
    query = apply_quote_list_scope(query, ctx, db)

    if active_view:
        query = apply_view_filters(query, db, ctx.tenant_id, "quote", active_view.filters)
        query = apply_view_search(query, "quote", active_view.search_q)
        query = apply_view_sort(query, "quote", active_view.sort)
    else:
        parsed_filters = parse_list_filters_param(filters)
        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "quote", parsed_filters)
            filters_applied = True
        elif status:
            query = query.filter(Quote.status == status)
        query = apply_view_search(query, "quote", q)
        sort_spec = None
        if sort_by:
            sort_spec = [{"field_key": sort_by, "dir": (sort_dir or "desc").lower()}]
        query = apply_view_sort(query, "quote", sort_spec)

    if customer_id is not None:
        query = query.filter(Quote.customer_id == customer_id)
    if deal_id is not None:
        query = query.filter(Quote.deal_id == deal_id)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return QuoteListResponse(
        items=[QuoteOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        list_fields=resolve_view_list_columns(db, ctx.tenant_id, ctx.user.id, "quote", active_view),
        view_id=active_view.id if active_view else None,
        filters_applied=filters_applied if filters else None,
    )


@router.post("", response_model=QuoteOut, status_code=201)
def post_quote(
    body: QuoteCreate,
    ctx: TenantContext = Depends(require_permission("crm.quote.create")),
    db: Session = Depends(get_db),
):
    q = create_quote(db, ctx, body)
    return QuoteOut.model_validate(q)


@router.get("/{quote_id}", response_model=QuoteOut)
def get_quote_detail(
    quote_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.quote.view")),
    db: Session = Depends(get_db),
):
    q = require_quote(db, ctx, quote_id)
    return QuoteOut.model_validate(q)


@router.patch("/{quote_id}", response_model=QuoteOut)
def patch_quote(
    quote_id: UUID,
    body: QuoteUpdate,
    ctx: TenantContext = Depends(require_permission("crm.quote.edit")),
    db: Session = Depends(get_db),
):
    q = require_quote(db, ctx, quote_id)
    q = update_quote(db, ctx, q, body)
    return QuoteOut.model_validate(q)


@router.post("/{quote_id}/send", response_model=QuoteOut)
def send_quote_endpoint(
    quote_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.quote.send")),
    db: Session = Depends(get_db),
):
    q = require_quote(db, ctx, quote_id)
    q = send_quote(db, ctx, q)
    return QuoteOut.model_validate(q)


@router.post("/{quote_id}/accept", response_model=QuoteOut)
def accept_quote_endpoint(
    quote_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.quote.accept")),
    db: Session = Depends(get_db),
):
    q = require_quote(db, ctx, quote_id)
    q = accept_quote(db, ctx, q)
    return QuoteOut.model_validate(q)


@router.post("/{quote_id}/convert-to-order", response_model=QuoteConvertToOrderOut, status_code=201)
def convert_quote_to_order_endpoint(
    quote_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.convert")),
    db: Session = Depends(get_db),
):
    q = require_quote(db, ctx, quote_id)
    order = convert_quote_to_order(db, ctx, q)
    return QuoteConvertToOrderOut(quote_id=q.id, order_id=order.id)


@router.delete("/{quote_id}", status_code=204)
def delete_quote_endpoint(
    quote_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.quote.delete")),
    db: Session = Depends(get_db),
):
    q = require_quote(db, ctx, quote_id)
    soft_delete_quote(db, q)
