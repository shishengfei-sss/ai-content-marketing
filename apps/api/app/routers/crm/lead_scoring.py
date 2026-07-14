"""线索评分规则 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import LeadScoringRuleCreate, LeadScoringRuleOut, LeadScoringRuleUpdate
from app.services.crm import lead_scoring_service
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/lead-scoring", tags=["crm-lead-scoring"])


@router.get("/rules", response_model=list[LeadScoringRuleOut])
def api_list_rules(
    ctx: TenantContext = Depends(
        require_any_permission("crm.lead.edit", "crm.lead.list_all", "crm.pipeline.manage")
    ),
    db: Session = Depends(get_db),
):
    return lead_scoring_service.list_rules(db, ctx.tenant_id)


@router.post("/rules", response_model=LeadScoringRuleOut, status_code=201)
def api_create_rule(
    body: LeadScoringRuleCreate,
    ctx: TenantContext = Depends(require_any_permission("crm.lead.edit", "crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    return lead_scoring_service.create_rule(
        db,
        ctx,
        name=body.name,
        condition_json=body.condition_json,
        score_value=body.score_value,
        priority=body.priority,
        is_active=body.is_active,
    )


@router.put("/rules/{rule_id}", response_model=LeadScoringRuleOut)
def api_update_rule(
    rule_id: UUID,
    body: LeadScoringRuleUpdate,
    ctx: TenantContext = Depends(require_any_permission("crm.lead.edit", "crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    rule = lead_scoring_service.require_rule(db, ctx.tenant_id, rule_id)
    return lead_scoring_service.update_rule(
        db,
        ctx,
        rule,
        name=body.name,
        condition_json=body.condition_json,
        score_value=body.score_value,
        priority=body.priority,
        is_active=body.is_active,
    )


@router.delete("/rules/{rule_id}", status_code=204)
def api_delete_rule(
    rule_id: UUID,
    ctx: TenantContext = Depends(require_any_permission("crm.lead.edit", "crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    rule = lead_scoring_service.require_rule(db, ctx.tenant_id, rule_id)
    lead_scoring_service.delete_rule(db, ctx, rule)
