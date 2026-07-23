"""实体自动编号规则 API（v0.8）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_deals import EntityNumberRuleCreate, EntityNumberRuleOut, EntityNumberRuleUpdate
from app.services.crm.number_service import create_rule, delete_rule, list_rules, update_rule
from app.services.permission_service import require_permission

router = APIRouter(prefix="/number-rules", tags=["crm-number-rules"])


def _rule_out(r) -> EntityNumberRuleOut:
    return EntityNumberRuleOut(
        entity_type=r.entity_type,
        prefix=r.prefix,
        suffix=getattr(r, "suffix", None) or "",
        date_format=r.date_format,
        seq_width=r.seq_width,
        reset_period=r.reset_period,
        enabled=r.enabled,
    )


@router.get("", response_model=list[EntityNumberRuleOut])
def list_number_rules(
    ctx: TenantContext = Depends(require_permission("crm.deal.list_own")),
    db: Session = Depends(get_db),
):
    return [_rule_out(r) for r in list_rules(db, ctx.tenant_id)]


@router.post("", response_model=EntityNumberRuleOut, status_code=201)
def create_number_rule(
    data: EntityNumberRuleCreate,
    ctx: TenantContext = Depends(require_permission("crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    try:
        rule = create_rule(
            db,
            ctx.tenant_id,
            entity_type=data.entity_type,
            prefix=data.prefix,
            suffix=data.suffix,
            date_format=data.date_format,
            seq_width=data.seq_width,
            reset_period=data.reset_period,
            enabled=data.enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    return _rule_out(rule)


@router.put("/{entity_type}", response_model=EntityNumberRuleOut)
def update_number_rule(
    entity_type: str,
    data: EntityNumberRuleUpdate,
    ctx: TenantContext = Depends(require_permission("crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    try:
        rule = update_rule(
            db,
            ctx.tenant_id,
            entity_type,
            prefix=data.prefix,
            suffix=data.suffix,
            date_format=data.date_format,
            seq_width=data.seq_width,
            reset_period=data.reset_period,
            enabled=data.enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    return _rule_out(rule)


@router.delete("/{entity_type}", status_code=204)
def delete_number_rule(
    entity_type: str,
    ctx: TenantContext = Depends(require_permission("crm.pipeline.manage")),
    db: Session = Depends(get_db),
):
    try:
        delete_rule(db, ctx.tenant_id, entity_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    db.commit()
