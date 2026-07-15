"""订单审批规则 API（v1.0 P0）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_deals import (
    OrderApprovalRuleCreate,
    OrderApprovalRuleOut,
    OrderApprovalRuleUpdate,
)
from app.services.crm.order_service import (
    create_approval_rule,
    delete_approval_rule,
    get_approval_rule,
    list_approval_rules,
    update_approval_rule,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/approval-rules", tags=["crm-approval-rules"])


@router.get("", response_model=list[OrderApprovalRuleOut])
def get_approval_rules(
    ctx: TenantContext = Depends(require_permission("crm.order.view")),
    db: Session = Depends(get_db),
):
    return [OrderApprovalRuleOut.model_validate(r) for r in list_approval_rules(db, ctx.tenant_id)]


@router.post("", response_model=OrderApprovalRuleOut, status_code=201)
def post_approval_rule(
    body: OrderApprovalRuleCreate,
    ctx: TenantContext = Depends(require_permission("crm.order.approve")),
    db: Session = Depends(get_db),
):
    rule = create_approval_rule(db, ctx, body)
    return OrderApprovalRuleOut.model_validate(rule)


@router.patch("/{rule_id}", response_model=OrderApprovalRuleOut)
def patch_approval_rule(
    rule_id: UUID,
    body: OrderApprovalRuleUpdate,
    ctx: TenantContext = Depends(require_permission("crm.order.approve")),
    db: Session = Depends(get_db),
):
    rule = get_approval_rule(db, ctx.tenant_id, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="审批规则不存在")
    rule = update_approval_rule(db, rule, body)
    return OrderApprovalRuleOut.model_validate(rule)


@router.delete("/{rule_id}", status_code=204)
def delete_approval_rule_endpoint(
    rule_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.approve")),
    db: Session = Depends(get_db),
):
    rule = get_approval_rule(db, ctx.tenant_id, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="审批规则不存在")
    delete_approval_rule(db, rule)
