"""线索 API。"""

from __future__ import annotations



from uuid import UUID



from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy.orm import Session



from app.database import get_db

from app.dependencies import TenantContext

from app.models.crm import Lead

from app.schemas.crm import LeadCreate, LeadListResponse, LeadOut, LeadUpdate, LeadConvertOut

from app.services.crm.crm_scope_service import apply_lead_list_scope, has_lead_list_permission

from app.services.crm.lead_service import (

    convert_lead_to_customer,

    create_lead,

    require_lead,

    soft_delete_lead,

    update_lead,

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



router = APIRouter(prefix="/leads", tags=["crm-leads"])





@router.get("", response_model=LeadListResponse)

def list_leads(

    page: int = Query(default=1, ge=1),

    page_size: int = Query(default=20, ge=1, le=100),

    owner_id: UUID | None = Query(default=None),

    view_id: UUID | None = Query(default=None),

    q: str | None = Query(default=None),

    status: str | None = Query(default=None),

    filters: str | None = Query(default=None, description="高级筛选 JSON"),

    campaign_id: UUID | None = Query(default=None),

    sort_by: str | None = Query(default=None),

    sort_dir: str | None = Query(default=None, pattern="^(asc|desc)$"),

    ctx: TenantContext = Depends(

        require_any_permission(

            "crm.lead.list_own",

            "crm.lead.list_team",

            "crm.lead.list_territory",

            "crm.lead.list_all",

        )

    ),

    db: Session = Depends(get_db),

):

    if not has_lead_list_permission(ctx):

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")



    active_view = None
    filters_applied = False

    if view_id is not None:

        active_view = get_view(db, ctx.tenant_id, view_id)

        if not active_view:

            raise HTTPException(status_code=404, detail="视图不存在")

        assert_can_access_view(ctx, active_view)



    query = db.query(Lead).filter(Lead.tenant_id == ctx.tenant_id, Lead.deleted_at.is_(None))

    query = apply_lead_list_scope(query, ctx, db)



    if active_view:

        query = apply_view_filters(query, db, ctx.tenant_id, "lead", active_view.filters)

        query = apply_view_search(query, "lead", active_view.search_q)

        query = apply_view_sort(query, "lead", active_view.sort)

    else:

        parsed_filters = parse_list_filters_param(filters)

        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "lead", parsed_filters)
            filters_applied = True

        elif status:

            query = query.filter(Lead.status == status)

        query = apply_view_search(query, "lead", q)

        sort_spec = None
        if sort_by:
            sort_spec = [{"field_key": sort_by, "dir": (sort_dir or "desc").lower()}]
        query = apply_view_sort(query, "lead", sort_spec)



    if owner_id is not None:

        query = query.filter(Lead.owner_user_id == owner_id)



    if campaign_id is not None:

        query = query.filter(Lead.campaign_id == campaign_id)



    total = query.count()

    items = query.offset((page - 1) * page_size).limit(page_size).all()



    return LeadListResponse(

        items=[LeadOut.model_validate(i) for i in items],

        total=total,

        page=page,

        page_size=page_size,

        list_fields=resolve_view_list_columns(db, ctx.tenant_id, ctx.user.id, "lead", active_view),

        view_id=active_view.id if active_view else None,

        filters_applied=filters_applied if filters else None,

    )





@router.post("", response_model=LeadOut, status_code=201)

def post_lead(

    body: LeadCreate,

    ctx: TenantContext = Depends(require_permission("crm.lead.create")),

    db: Session = Depends(get_db),

):

    lead = create_lead(db, ctx, body)

    return LeadOut.model_validate(lead)





@router.get("/{lead_id}", response_model=LeadOut)

def get_lead_detail(

    lead_id: UUID,

    ctx: TenantContext = Depends(require_permission("crm.lead.view")),

    db: Session = Depends(get_db),

):

    lead = require_lead(db, ctx, lead_id)

    return LeadOut.model_validate(lead)





@router.patch("/{lead_id}", response_model=LeadOut)

def patch_lead(

    lead_id: UUID,

    body: LeadUpdate,

    ctx: TenantContext = Depends(require_permission("crm.lead.edit")),

    db: Session = Depends(get_db),

):

    lead = require_lead(db, ctx, lead_id)

    lead = update_lead(db, ctx, lead, body)

    return LeadOut.model_validate(lead)





@router.post("/{lead_id}/convert", response_model=LeadConvertOut, status_code=201)

def convert_lead(

    lead_id: UUID,

    ctx: TenantContext = Depends(require_permission("crm.lead.convert")),

    db: Session = Depends(get_db),

):

    lead = require_lead(db, ctx, lead_id)

    customer, contact = convert_lead_to_customer(db, ctx, lead)

    return LeadConvertOut(

        lead_id=lead.id,

        customer_id=customer.id,

        contact_id=contact.id if contact else None,

    )





@router.delete("/{lead_id}", status_code=204)

def delete_lead(

    lead_id: UUID,

    ctx: TenantContext = Depends(require_permission("crm.lead.delete")),

    db: Session = Depends(get_db),

):

    lead = require_lead(db, ctx, lead_id)

    soft_delete_lead(db, lead)

