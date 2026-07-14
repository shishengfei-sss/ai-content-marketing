"""线索培育规则 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import NurtureRuleCreate, NurtureRuleOut
from app.services.crm import nurture_service
from app.services.permission_service import require_any_permission

router = APIRouter(prefix="/nurture-rules", tags=["crm-nurture"])


@router.get("", response_model=list[NurtureRuleOut])
def api_list_rules(
    ctx: TenantContext = Depends(
        require_any_permission("crm.lead.edit", "crm.lead.list_all", "crm.pipeline.manage")
    ),
    db: Session = Depends(get_db),
):
    return nurture_service.list_rules(db, ctx.tenant_id)


@router.post("", response_model=NurtureRuleOut, status_code=201)
def api_create_rule(
    body: NurtureRuleCreate,
    ctx: TenantContext = Depends(require_any_permission("crm.lead.edit", "crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    return nurture_service.create_rule(
        db,
        ctx,
        name=body.name,
        condition_json=body.condition_json,
        action_type=body.action_type,
        action_config=body.action_config,
        priority=body.priority,
        is_active=body.is_active,
    )


@router.post("/run")
def api_run_rules(
    limit: int = Query(default=200, ge=1, le=1000),
    ctx: TenantContext = Depends(require_any_permission("crm.lead.edit", "crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    return nurture_service.run_nurture_rules(db, ctx, limit=limit)


@router.delete("/{rule_id}", status_code=204)
def api_delete_rule(
    rule_id: UUID,
    ctx: TenantContext = Depends(require_any_permission("crm.lead.edit", "crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    rule = nurture_service.require_rule(db, ctx.tenant_id, rule_id)
    nurture_service.delete_rule(db, ctx, rule)
