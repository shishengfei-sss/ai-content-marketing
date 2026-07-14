"""自动分配规则 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import AssignmentRuleCreate, AssignmentRuleOut, AssignmentRuleUpdate
from app.services.crm import assignment_service
from app.services.permission_service import require_any_permission

router = APIRouter(prefix="/assignment-rules", tags=["crm-assignment-rules"])


@router.get("", response_model=list[AssignmentRuleOut])
def api_list(
    ctx: TenantContext = Depends(require_any_permission("crm.lead.edit", "crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    return assignment_service.list_rules(db, ctx.tenant_id)


@router.post("", response_model=AssignmentRuleOut, status_code=201)
def api_create(
    body: AssignmentRuleCreate,
    ctx: TenantContext = Depends(require_any_permission("crm.lead.edit", "crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    return assignment_service.create_rule(
        db,
        ctx,
        name=body.name,
        condition_json=body.condition_json,
        assign_type=body.assign_type,
        target_id=body.target_id,
        priority=body.priority,
        is_active=body.is_active,
    )


@router.patch("/{rule_id}", response_model=AssignmentRuleOut)
def api_update(
    rule_id: UUID,
    body: AssignmentRuleUpdate,
    ctx: TenantContext = Depends(require_any_permission("crm.lead.edit", "crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    rule = assignment_service.require_rule(db, ctx.tenant_id, rule_id)
    return assignment_service.update_rule(
        db,
        ctx,
        rule,
        name=body.name,
        condition_json=body.condition_json,
        assign_type=body.assign_type,
        target_id=body.target_id,
        priority=body.priority,
        is_active=body.is_active,
    )


@router.delete("/{rule_id}", status_code=204)
def api_delete(
    rule_id: UUID,
    ctx: TenantContext = Depends(require_any_permission("crm.lead.edit", "crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    rule = assignment_service.require_rule(db, ctx.tenant_id, rule_id)
    assignment_service.delete_rule(db, ctx, rule)
