"""线索自动分配规则。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import TenantMembership
from app.models.crm import AssignmentRule, Lead, MembershipSalesProfile
from app.services.crm.lead_scoring_service import match_condition

ASSIGN_TYPES = frozenset({"fixed_user", "round_robin", "load_balanced", "lead_creator"})


def list_rules(db: Session, tenant_id: UUID) -> list[AssignmentRule]:
    return (
        db.query(AssignmentRule)
        .filter(AssignmentRule.tenant_id == tenant_id)
        .order_by(AssignmentRule.priority.asc(), AssignmentRule.created_at.asc())
        .all()
    )


def require_rule(db: Session, tenant_id: UUID, rule_id: UUID) -> AssignmentRule:
    rule = (
        db.query(AssignmentRule)
        .filter(uuid_eq(AssignmentRule.id, rule_id), AssignmentRule.tenant_id == tenant_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="分配规则不存在")
    return rule


def create_rule(
    db: Session,
    ctx: TenantContext,
    *,
    name: str,
    condition_json: dict,
    assign_type: str,
    target_id: UUID | None = None,
    priority: int = 0,
    is_active: bool = True,
) -> AssignmentRule:
    if assign_type not in ASSIGN_TYPES:
        raise HTTPException(status_code=400, detail=f"assign_type 必须是 {sorted(ASSIGN_TYPES)} 之一")
    if assign_type == "fixed_user" and target_id is None:
        raise HTTPException(status_code=400, detail="fixed_user 必须指定 target_id")
    if assign_type == "lead_creator":
        target_id = None
    rule = AssignmentRule(
        tenant_id=ctx.tenant_id,
        name=name.strip(),
        condition_json=condition_json or {},
        assign_type=assign_type,
        target_id=target_id,
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
    rule: AssignmentRule,
    *,
    name: str | None = None,
    condition_json: dict | None = None,
    assign_type: str | None = None,
    target_id: UUID | None = None,
    priority: int | None = None,
    is_active: bool | None = None,
) -> AssignmentRule:
    if name is not None:
        rule.name = name.strip()
    if condition_json is not None:
        rule.condition_json = condition_json
    if assign_type is not None:
        if assign_type not in ASSIGN_TYPES:
            raise HTTPException(status_code=400, detail=f"assign_type 必须是 {sorted(ASSIGN_TYPES)} 之一")
        rule.assign_type = assign_type
        if assign_type == "lead_creator":
            rule.target_id = None
            target_id = None
        elif assign_type == "fixed_user" and target_id is None and rule.target_id is None:
            raise HTTPException(status_code=400, detail="fixed_user 必须指定 target_id")
    if target_id is not None:
        rule.target_id = target_id
    if priority is not None:
        rule.priority = priority
    if is_active is not None:
        rule.is_active = is_active
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, ctx: TenantContext, rule: AssignmentRule) -> None:
    db.delete(rule)
    db.commit()


def _scope_territory_id(rule: AssignmentRule, lead: Lead | None) -> UUID | None:
    """轮询候选范围：优先线索销售区域，其次条件里的销售区域。"""
    if lead is not None and lead.territory_id is not None:
        return lead.territory_id
    cond = rule.condition_json or {}
    if cond.get("field") == "territory_id":
        op = cond.get("operator") or cond.get("op")
        if op in ("equals", "eq") and cond.get("value") not in (None, ""):
            try:
                return UUID(str(cond["value"]))
            except (TypeError, ValueError):
                return None
    return None


def _candidate_user_ids(
    db: Session,
    tenant_id: UUID,
    rule: AssignmentRule,
    *,
    lead: Lead | None = None,
) -> list[UUID]:
    cond = rule.condition_json or {}
    raw = cond.get("candidates") or cond.get("candidate_user_ids")
    if isinstance(raw, list) and raw:
        return [UUID(str(x)) for x in raw]

    scope_tid = _scope_territory_id(rule, lead)
    if scope_tid is not None:
        rows = (
            db.query(TenantMembership.user_id)
            .join(
                MembershipSalesProfile,
                MembershipSalesProfile.membership_id == TenantMembership.id,
            )
            .filter(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_active.is_(True),
                uuid_eq(MembershipSalesProfile.primary_territory_id, scope_tid),
            )
            .order_by(TenantMembership.joined_at.asc())
            .all()
        )
        return [r[0] for r in rows]

    rows = (
        db.query(TenantMembership.user_id)
        .filter(TenantMembership.tenant_id == tenant_id, TenantMembership.is_active.is_(True))
        .order_by(TenantMembership.joined_at.asc())
        .all()
    )
    return [r[0] for r in rows]


def _pick_round_robin(db: Session, tenant_id: UUID, candidates: list[UUID]) -> UUID | None:
    if not candidates:
        return None
    counts = {
        uid: db.query(func.count(Lead.id))
        .filter(Lead.tenant_id == tenant_id, Lead.owner_user_id == uid, Lead.deleted_at.is_(None))
        .scalar()
        or 0
        for uid in candidates
    }
    # 选线索数最少者中靠前的（近似 round robin）
    return min(candidates, key=lambda u: (counts.get(u, 0), str(u)))


def _pick_load_balanced(db: Session, tenant_id: UUID, candidates: list[UUID]) -> UUID | None:
    return _pick_round_robin(db, tenant_id, candidates)


def resolve_owner_for_lead(db: Session, tenant_id: UUID, lead: Lead) -> UUID | None:
    rules = (
        db.query(AssignmentRule)
        .filter(AssignmentRule.tenant_id == tenant_id, AssignmentRule.is_active.is_(True))
        .order_by(AssignmentRule.priority.asc(), AssignmentRule.created_at.asc())
        .all()
    )
    for rule in rules:
        if not match_condition(lead, rule.condition_json or {}):
            continue
        if rule.assign_type == "lead_creator":
            return lead.created_by_user_id
        if rule.assign_type == "fixed_user" and rule.target_id:
            return rule.target_id
        candidates = _candidate_user_ids(db, tenant_id, rule, lead=lead)
        if rule.target_id and rule.target_id not in candidates:
            candidates = [rule.target_id] + candidates
        if rule.assign_type == "round_robin":
            owner = _pick_round_robin(db, tenant_id, candidates)
            if owner is not None:
                return owner
            continue
        if rule.assign_type == "load_balanced":
            owner = _pick_load_balanced(db, tenant_id, candidates)
            if owner is not None:
                return owner
            continue
    return None


def apply_assignment_rules(db: Session, ctx: TenantContext, lead: Lead) -> Lead:
    owner = resolve_owner_for_lead(db, ctx.tenant_id, lead)
    if owner is not None:
        prev = lead.owner_user_id
        lead.owner_user_id = owner
        if owner != prev:
            from app.services.crm.sales_org_service import apply_owner_org_snapshot

            # 与手动分配一致：同步新负责人的销售区域 / 汇报上级，避免原地区人员仍可见
            snap_territory, snap_manager = apply_owner_org_snapshot(db, ctx.tenant_id, owner)
            lead.territory_id = snap_territory
            lead.manager_user_id = snap_manager
        db.flush()
        if owner != prev and owner != ctx.user.id:
            from app.services.crm.notification_service import create_notification

            create_notification(
                db,
                tenant_id=ctx.tenant_id,
                user_id=owner,
                title="新线索已分配给你",
                body=f"「{lead.company_name}」已按分配规则指派给你",
                category="assignment",
                entity_type="lead",
                entity_id=lead.id,
                commit=False,
            )
    return lead
