"""线索评分规则服务。"""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Lead, LeadScoringRule


SUPPORTED_OPERATORS = frozenset({"equals", "contains", "in", "gt", "lt", "gte", "lte", "regex"})


def _field_value(lead: Lead, field: str):
    if hasattr(lead, field):
        return getattr(lead, field)
    extra = lead.extra_data or {}
    return extra.get(field)


def match_condition(lead: Lead, condition: dict | None) -> bool:
    if not condition:
        return False
    field = condition.get("field")
    op = condition.get("operator") or condition.get("op")
    expected = condition.get("value")
    if not field or not op:
        return False
    if op not in SUPPORTED_OPERATORS:
        return False
    actual = _field_value(lead, field)
    if op == "equals":
        if actual is None and expected is None:
            return True
        if actual is None or expected is None:
            return False
        # UUID 与字符串可比（分配规则条件常为字符串）
        return str(actual) == str(expected)
    if op == "contains":
        return actual is not None and expected is not None and str(expected) in str(actual)
    if op == "in":
        if not isinstance(expected, (list, tuple, set)):
            return False
        if actual is None:
            return False
        return str(actual) in {str(x) for x in expected}
    if op in {"gt", "lt", "gte", "lte"}:
        try:
            a = float(actual)
            b = float(expected)
        except (TypeError, ValueError):
            return False
        if op == "gt":
            return a > b
        if op == "lt":
            return a < b
        if op == "gte":
            return a >= b
        return a <= b
    if op == "regex":
        if actual is None or expected is None:
            return False
        try:
            return re.search(str(expected), str(actual)) is not None
        except re.error:
            return False
    return False


def calculate_lead_score(db: Session, tenant_id: UUID, lead: Lead) -> int:
    rules = (
        db.query(LeadScoringRule)
        .filter(
            LeadScoringRule.tenant_id == tenant_id,
            LeadScoringRule.is_active.is_(True),
        )
        .order_by(LeadScoringRule.priority.asc(), LeadScoringRule.created_at.asc())
        .all()
    )
    total = 0
    for rule in rules:
        if match_condition(lead, rule.condition_json or {}):
            total += int(rule.score_value or 0)
    return min(max(total, 0), 100)


def recalculate_lead_score(db: Session, ctx: TenantContext, lead: Lead) -> Lead:
    from app.services.tender_match_service import get_icp, score_crm_lead

    lead.lead_score = calculate_lead_score(db, ctx.tenant_id, lead)
    icp = get_icp(db, ctx.tenant_id)
    lead.icp_score = score_crm_lead(lead, icp) if icp and getattr(icp, "is_active", True) else 0
    db.commit()
    db.refresh(lead)
    return lead


def list_rules(db: Session, tenant_id: UUID) -> list[LeadScoringRule]:
    return (
        db.query(LeadScoringRule)
        .filter(LeadScoringRule.tenant_id == tenant_id)
        .order_by(LeadScoringRule.priority.asc(), LeadScoringRule.created_at.asc())
        .all()
    )


def get_rule(db: Session, tenant_id: UUID, rule_id: UUID) -> LeadScoringRule | None:
    return (
        db.query(LeadScoringRule)
        .filter(uuid_eq(LeadScoringRule.id, rule_id), LeadScoringRule.tenant_id == tenant_id)
        .first()
    )


def require_rule(db: Session, tenant_id: UUID, rule_id: UUID) -> LeadScoringRule:
    rule = get_rule(db, tenant_id, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="评分规则不存在")
    return rule


def create_rule(
    db: Session,
    ctx: TenantContext,
    *,
    name: str,
    condition_json: dict,
    score_value: int,
    priority: int = 0,
    is_active: bool = True,
) -> LeadScoringRule:
    op = (condition_json or {}).get("operator") or (condition_json or {}).get("op")
    if op and op not in SUPPORTED_OPERATORS:
        raise HTTPException(status_code=400, detail=f"不支持的运算符: {op}")
    rule = LeadScoringRule(
        tenant_id=ctx.tenant_id,
        name=name.strip(),
        condition_json=condition_json or {},
        score_value=score_value,
        priority=priority,
        is_active=is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(
    db: Session,
    ctx: TenantContext,
    rule: LeadScoringRule,
    *,
    name: str | None = None,
    condition_json: dict | None = None,
    score_value: int | None = None,
    priority: int | None = None,
    is_active: bool | None = None,
) -> LeadScoringRule:
    if name is not None:
        rule.name = name.strip()
    if condition_json is not None:
        op = condition_json.get("operator") or condition_json.get("op")
        if op and op not in SUPPORTED_OPERATORS:
            raise HTTPException(status_code=400, detail=f"不支持的运算符: {op}")
        rule.condition_json = condition_json
    if score_value is not None:
        rule.score_value = score_value
    if priority is not None:
        rule.priority = priority
    if is_active is not None:
        rule.is_active = is_active
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, ctx: TenantContext, rule: LeadScoringRule) -> None:
    db.delete(rule)
    db.commit()
