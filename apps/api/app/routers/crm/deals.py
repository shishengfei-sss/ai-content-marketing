"""商机 API（v0.7 CRM-2）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.models.crm import Deal
from app.schemas.crm import ActivityCreate, ActivityOut, validate_activity_type
from app.schemas.crm_deals import (
    DealBatchUpdate,
    DealClose,
    DealConvertToOrderOut,
    DealCreate,
    DealCloneOut,
    DealListResponse,
    DealOut,
    DealStageChange,
    DealStageLogOut,
    DealTeamMemberAdd,
    DealTeamMemberOut,
    DealUpdate,
    QuoteOut,
)
from app.services.crm.crm_scope_service import apply_deal_list_scope, has_deal_list_permission
from app.services.crm.activity_service import create_activity, list_activities
from app.services.crm.deal_service import (
    batch_update_deals,
    change_stage,
    close_deal,
    clone_deal,
    convert_deal_to_order,
    create_deal,
    add_team_member,
    deal_to_out,
    enrich_deals_stage_stay,
    list_team_members,
    generate_quote_from_deal,
    remove_team_member,
    list_stage_logs,
    require_deal,
    soft_delete_deal,
    update_deal,
)
from app.services.crm.filter_query import parse_list_filters_param
from app.services.crm.view_service import (
    apply_view_filters,
    apply_view_search,
    apply_view_sort,
    assert_can_access_view,
    get_view,
    resolve_view_list_columns,
)
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/deals", tags=["crm-deals"])


@router.get("", response_model=DealListResponse)
def list_deals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    owner_id: UUID | None = Query(default=None),
    view_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    pipeline_id: UUID | None = Query(default=None),
    stage_id: UUID | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),
    filters: str | None = Query(default=None, description="高级筛选 JSON"),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None, pattern="^(asc|desc)$"),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.deal.list_own",
            "crm.deal.list_team",
            "crm.deal.list_territory",
            "crm.deal.list_all",
        )
    ),
    db: Session = Depends(get_db),
):
    if not has_deal_list_permission(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")

    active_view = None
    filters_applied = False
    if view_id is not None:
        active_view = get_view(db, ctx.tenant_id, view_id)
        if not active_view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, active_view)

    query = db.query(Deal).filter(Deal.tenant_id == ctx.tenant_id, Deal.deleted_at.is_(None))
    query = apply_deal_list_scope(query, ctx, db)

    if active_view:
        query = apply_view_filters(query, db, ctx.tenant_id, "deal", active_view.filters)
        query = apply_view_search(query, "deal", active_view.search_q)
        query = apply_view_sort(query, "deal", active_view.sort)
    else:
        parsed_filters = parse_list_filters_param(filters)
        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "deal", parsed_filters)
            filters_applied = True
        elif status:
            query = query.filter(Deal.status == status)
        query = apply_view_search(query, "deal", q)
        sort_spec = None
        if sort_by:
            sort_spec = [{"field_key": sort_by, "dir": (sort_dir or "desc").lower()}]
        query = apply_view_sort(query, "deal", sort_spec)

    if owner_id is not None:
        query = query.filter(Deal.owner_user_id == owner_id)
    if pipeline_id is not None:
        query = query.filter(Deal.pipeline_id == pipeline_id)
    if stage_id is not None:
        query = query.filter(Deal.stage_id == stage_id)
    if customer_id is not None:
        query = query.filter(Deal.customer_id == customer_id)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return DealListResponse(
        items=enrich_deals_stage_stay(db, ctx.tenant_id, items),
        total=total,
        page=page,
        page_size=page_size,
        list_fields=resolve_view_list_columns(db, ctx.tenant_id, ctx.user.id, "deal", active_view),
        view_id=active_view.id if active_view else None,
        filters_applied=filters_applied if filters else None,
    )


@router.post("", response_model=DealOut, status_code=201)
def post_deal(
    body: DealCreate,
    ctx: TenantContext = Depends(require_permission("crm.deal.create")),
    db: Session = Depends(get_db),
):
    deal = create_deal(db, ctx, body)
    return DealOut.model_validate(deal)


@router.get("/{deal_id}", response_model=DealOut)
def get_deal_detail(
    deal_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.deal.view")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    return deal_to_out(db, ctx.tenant_id, deal)


@router.post("/batch-update")
def batch_update_deals_endpoint(
    body: DealBatchUpdate,
    ctx: TenantContext = Depends(require_permission("crm.deal.edit")),
    db: Session = Depends(get_db),
):
    count = batch_update_deals(db, ctx, body)
    return {"updated": count}


@router.post("/{deal_id}/clone", response_model=DealCloneOut, status_code=201)
def clone_deal_endpoint(
    deal_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.deal.create")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    cloned = clone_deal(db, ctx, deal)
    return DealCloneOut(source_deal_id=deal.id, deal_id=cloned.id)


@router.patch("/{deal_id}", response_model=DealOut)
def patch_deal(
    deal_id: UUID,
    body: DealUpdate,
    ctx: TenantContext = Depends(require_permission("crm.deal.edit")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    deal = update_deal(db, ctx, deal, body)
    return DealOut.model_validate(deal)


@router.post("/{deal_id}/stage", response_model=DealOut)
def change_deal_stage(
    deal_id: UUID,
    body: DealStageChange,
    ctx: TenantContext = Depends(require_permission("crm.deal.edit")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    deal = change_stage(db, ctx, deal, body)
    return DealOut.model_validate(deal)


@router.post("/{deal_id}/close", response_model=DealOut)
def close_deal_endpoint(
    deal_id: UUID,
    body: DealClose,
    ctx: TenantContext = Depends(require_permission("crm.deal.close")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    deal = close_deal(db, ctx, deal, body)
    return DealOut.model_validate(deal)


@router.get("/{deal_id}/stage-logs", response_model=list[DealStageLogOut])
def list_deal_stage_logs(
    deal_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.deal.view")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    logs = list_stage_logs(db, ctx.tenant_id, deal.id)
    return [DealStageLogOut.model_validate(log) for log in logs]


@router.get("/{deal_id}/activities", response_model=list[ActivityOut])
def list_deal_activities(
    deal_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.deal.view")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    items = list_activities(db, ctx, deal_id=deal.id)
    return [ActivityOut.model_validate(i) for i in items]


@router.post("/{deal_id}/activities", response_model=ActivityOut, status_code=201)
def create_deal_activity(
    deal_id: UUID,
    body: ActivityCreate,
    ctx: TenantContext = Depends(require_permission("crm.activity.create")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    body = body.model_copy(update={"deal_id": deal.id, "lead_id": None, "customer_id": None})
    try:
        validate_activity_type(body.activity_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    activity = create_activity(db, ctx, body)
    return ActivityOut.model_validate(activity)


@router.post("/{deal_id}/convert-to-order", response_model=DealConvertToOrderOut, status_code=201)
def convert_deal_to_order_endpoint(
    deal_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.convert")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    order = convert_deal_to_order(db, ctx, deal)
    return DealConvertToOrderOut(deal_id=deal.id, order_id=order.id)


@router.post("/{deal_id}/generate-quote", response_model=QuoteOut, status_code=201)
def generate_deal_quote_endpoint(
    deal_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.quote.edit")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    quote = generate_quote_from_deal(db, ctx, deal)
    return QuoteOut.model_validate(quote)


@router.get("/{deal_id}/team", response_model=list[DealTeamMemberOut])
def list_deal_team_endpoint(
    deal_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.deal.view")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    members = list_team_members(db, ctx, deal)
    return [DealTeamMemberOut.model_validate(m) for m in members]


@router.post("/{deal_id}/team", response_model=DealTeamMemberOut, status_code=201)
def add_deal_team_endpoint(
    deal_id: UUID,
    body: DealTeamMemberAdd,
    ctx: TenantContext = Depends(require_permission("crm.deal.edit")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    member = add_team_member(db, ctx, deal, body.user_id, body.role)
    return DealTeamMemberOut.model_validate(member)


@router.delete("/{deal_id}/team/{member_id}", status_code=204)
def remove_deal_team_endpoint(
    deal_id: UUID,
    member_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.deal.edit")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    remove_team_member(db, ctx, deal, member_id)


@router.delete("/{deal_id}", status_code=204)
def delete_deal_endpoint(
    deal_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.deal.delete")),
    db: Session = Depends(get_db),
):
    deal = require_deal(db, ctx, deal_id)
    soft_delete_deal(db, deal)
