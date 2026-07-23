"""租户 ICP + 招标线索匹配池 L2 API。"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.tender_leads import (
    IcpConfigOut,
    IcpConfigUpsert,
    ScoredTenderLeadListResponse,
    ScoredTenderLeadOut,
    TenderAnalyticsOut,
    TenderClaimOut,
)
from app.services import tender_analytics_service, tender_match_service as svc
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(tags=["crm-tender-leads"])


@router.get("/tender-lead-analytics", response_model=TenderAnalyticsOut)
def tender_lead_analytics(
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.lead.list_all",
            "crm.lead.list_team",
            "crm.pipeline.manage",
            "analytics.view",
        )
    ),
    db: Session = Depends(get_db),
):
    return tender_analytics_service.get_tender_analytics(db, ctx)


@router.get("/icp-config", response_model=IcpConfigOut | None)
def get_icp_config(
    ctx: TenantContext = Depends(
        require_any_permission("crm.lead.view", "crm.lead.create", "crm.lead.list_own", "crm.lead.list_all")
    ),
    db: Session = Depends(get_db),
):
    row = svc.get_icp(db, ctx.tenant_id)
    return IcpConfigOut.model_validate(row) if row else None


@router.put("/icp-config", response_model=IcpConfigOut)
def put_icp_config(
    body: IcpConfigUpsert,
    ctx: TenantContext = Depends(require_any_permission("crm.lead.edit", "crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    try:
        row = svc.upsert_icp(db, ctx, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return IcpConfigOut.model_validate(row)


@router.get("/tender-leads", response_model=ScoredTenderLeadListResponse)
def list_tender_leads(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, description="采购方/标的/编号/代理/摘要关键词"),
    region: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    category: str | None = Query(default=None),
    procurement_method: str | None = Query(default=None),
    agent_name: str | None = Query(default=None),
    project_no: str | None = Query(default=None),
    sme_preference: bool | None = Query(default=None),
    deadline_from: date | None = Query(default=None),
    deadline_to: date | None = Query(default=None),
    min_score: int | None = Query(default=None, ge=0, le=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.lead.list_own",
            "crm.lead.list_team",
            "crm.lead.list_territory",
            "crm.lead.list_all",
            "crm.lead.view",
        )
    ),
    db: Session = Depends(get_db),
):
    items, total = svc.list_scored(
        db,
        ctx,
        status_filter=status,
        page=page,
        page_size=page_size,
        q=q,
        region=region,
        industry=industry,
        category=category,
        procurement_method=procurement_method,
        agent_name=agent_name,
        project_no=project_no,
        sme_preference=sme_preference,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        min_score=min_score,
    )
    return ScoredTenderLeadListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/tender-leads/{scored_id}", response_model=ScoredTenderLeadOut)
def get_tender_lead(
    scored_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.lead.view")),
    db: Session = Depends(get_db),
):
    row = svc.get_scored(db, ctx, scored_id)
    return svc.enrich_scored(db, row)


@router.post("/tender-leads/{scored_id}/claim", response_model=TenderClaimOut)
def claim_tender_lead(
    scored_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.lead.create")),
    db: Session = Depends(get_db),
):
    scored, lead = svc.claim_to_lead(db, ctx, scored_id)
    return TenderClaimOut(
        scored_tender_lead_id=scored.id,
        lead_id=lead.id,
        deal_created=False,
    )


@router.post("/tender-leads/{scored_id}/ignore", response_model=ScoredTenderLeadOut)
def ignore_tender_lead(
    scored_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.lead.edit")),
    db: Session = Depends(get_db),
):
    row = svc.set_scored_status(db, ctx, scored_id, "invalid")
    return svc.enrich_scored(db, row)
