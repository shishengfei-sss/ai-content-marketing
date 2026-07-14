"""线索培育规则（MVP：条件匹配 → 建任务/发通知）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Lead, NurtureRule
from app.schemas.crm import TaskCreate
from app.services.crm.lead_scoring_service import match_condition
from app.services.crm.notification_service import create_notification
from app.services.crm.task_service import create_task

ACTION_TYPES = frozenset({"create_task", "notify_owner"})


def list_rules(db: Session, tenant_id: UUID) -> list[NurtureRule]:
    return (
        db.query(NurtureRule)
        .filter(NurtureRule.tenant_id == tenant_id)
        .order_by(NurtureRule.priority.asc(), NurtureRule.created_at.asc())
        .all()
    )


def require_rule(db: Session, tenant_id: UUID, rule_id: UUID) -> NurtureRule:
    rule = (
        db.query(NurtureRule)
        .filter(uuid_eq(NurtureRule.id, rule_id), NurtureRule.tenant_id == tenant_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="培育规则不存在")
    return rule


def create_rule(
    db: Session,
    ctx: TenantContext,
    *,
    name: str,
    condition_json: dict,
    action_type: str,
    action_config: dict | None = None,
    priority: int = 0,
    is_active: bool = True,
) -> NurtureRule:
    if action_type not in ACTION_TYPES:
        raise HTTPException(status_code=400, detail=f"action_type 必须是 {sorted(ACTION_TYPES)}")
    rule = NurtureRule(
        tenant_id=ctx.tenant_id,
        name=name.strip(),
        condition_json=condition_json or {},
        action_type=action_type,
        action_config=action_config or {},
        priority=priority,
        is_active=is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, ctx: TenantContext, rule: NurtureRule) -> None:
    db.delete(rule)
    db.commit()


def _already_nurtured(lead: Lead, rule: NurtureRule) -> bool:
    extra = lead.extra_data or {}
    done = set(extra.get("_nurture_rule_ids") or [])
    return str(rule.id) in done


def _mark_nurtured(lead: Lead, rule: NurtureRule) -> None:
    extra = dict(lead.extra_data or {})
    done = list(extra.get("_nurture_rule_ids") or [])
    rid = str(rule.id)
    if rid not in done:
        done.append(rid)
    extra["_nurture_rule_ids"] = done
    lead.extra_data = extra


def run_nurture_rules(db: Session, ctx: TenantContext, *, limit: int = 200) -> dict:
    rules = (
        db.query(NurtureRule)
        .filter(NurtureRule.tenant_id == ctx.tenant_id, NurtureRule.is_active.is_(True))
        .order_by(NurtureRule.priority.asc())
        .all()
    )
    leads = (
        db.query(Lead)
        .filter(
            Lead.tenant_id == ctx.tenant_id,
            Lead.deleted_at.is_(None),
            Lead.status != "已转化",
        )
        .order_by(Lead.created_at.desc())
        .limit(limit)
        .all()
    )
    matched = 0
    actions = 0
    for lead in leads:
        for rule in rules:
            if _already_nurtured(lead, rule):
                continue
            if not match_condition(lead, rule.condition_json or {}):
                continue
            matched += 1
            cfg = rule.action_config or {}
            lead_id = lead.id
            owner_id = lead.owner_user_id
            company = lead.company_name
            if rule.action_type == "create_task":
                title = cfg.get("title") or f"培育跟进：{company}"
                create_task(
                    db,
                    ctx,
                    TaskCreate(
                        title=title,
                        description=cfg.get("description") or f"触发规则「{rule.name}」",
                        lead_id=lead_id,
                        assignee_user_id=owner_id or ctx.user.id,
                        status="open",
                        priority=cfg.get("priority") or "normal",
                    ),
                )
                actions += 1
            elif rule.action_type == "notify_owner" and owner_id:
                create_notification(
                    db,
                    tenant_id=ctx.tenant_id,
                    user_id=owner_id,
                    title=cfg.get("title") or "线索培育提醒",
                    body=cfg.get("body") or f"「{company}」命中培育规则「{rule.name}」",
                    category="nurture",
                    entity_type="lead",
                    entity_id=lead_id,
                    commit=False,
                )
                actions += 1
            lead = db.query(Lead).filter(uuid_eq(Lead.id, lead_id)).first()
            if lead:
                _mark_nurtured(lead, rule)
                db.commit()
            break  # 每线索每轮只触发一条规则
    return {"leads_scanned": len(leads), "matched": matched, "actions": actions}
