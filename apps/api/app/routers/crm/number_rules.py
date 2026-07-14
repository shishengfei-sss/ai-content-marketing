"""实体自动编号规则 API（v0.8）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_deals import EntityNumberRuleOut, EntityNumberRuleUpdate
from app.services.crm.number_service import list_rules, update_rule
from app.services.permission_service import require_permission

router = APIRouter(prefix="/number-rules", tags=["crm-number-rules"])


@router.get("", response_model=list[EntityNumberRuleOut])
def list_number_rules(
    ctx: TenantContext = Depends(require_permission("crm.deal.list_own")),
    db: Session = Depends(get_db),
):
    rules = list_rules(db, ctx.tenant_id)
    return [
        EntityNumberRuleOut(
            entity_type=r.entity_type,
            prefix=r.prefix,
            date_format=r.date_format,
            seq_width=r.seq_width,
            reset_period=r.reset_period,
            enabled=r.enabled,
        )
        for r in rules
    ]


@router.put("/{entity_type}", response_model=EntityNumberRuleOut)
def update_number_rule(
    entity_type: str,
    data: EntityNumberRuleUpdate,
    ctx: TenantContext = Depends(require_permission("crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    rule = update_rule(
        db,
        ctx.tenant_id,
        entity_type,
        prefix=data.prefix,
        date_format=data.date_format,
        seq_width=data.seq_width,
        reset_period=data.reset_period,
        enabled=data.enabled,
    )
    db.commit()
    return EntityNumberRuleOut(
        entity_type=rule.entity_type,
        prefix=rule.prefix,
        date_format=rule.date_format,
        seq_width=rule.seq_width,
        reset_period=rule.reset_period,
        enabled=rule.enabled,
    )
