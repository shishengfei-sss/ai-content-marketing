"""BANT 评估。"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import BantEvaluation, Lead


def _clamp_score(v: int) -> int:
    return max(1, min(5, int(v)))


def list_evaluations(db: Session, tenant_id: UUID, lead_id: UUID) -> list[BantEvaluation]:
    return (
        db.query(BantEvaluation)
        .filter(BantEvaluation.tenant_id == tenant_id, uuid_eq(BantEvaluation.lead_id, lead_id))
        .order_by(BantEvaluation.created_at.desc())
        .all()
    )


def latest_evaluation(db: Session, tenant_id: UUID, lead_id: UUID) -> BantEvaluation | None:
    rows = list_evaluations(db, tenant_id, lead_id)
    return rows[0] if rows else None


def create_evaluation(
    db: Session,
    ctx: TenantContext,
    lead: Lead,
    *,
    budget_score: int,
    authority_score: int,
    need_score: int,
    time_score: int,
    note: str | None = None,
    bump_lead_score: bool = True,
) -> BantEvaluation:
    b = _clamp_score(budget_score)
    a = _clamp_score(authority_score)
    n = _clamp_score(need_score)
    t = _clamp_score(time_score)
    total = round((b + a + n + t) / 4, 1)
    row = BantEvaluation(
        tenant_id=ctx.tenant_id,
        lead_id=lead.id,
        budget_score=b,
        authority_score=a,
        need_score=n,
        time_score=t,
        total_score=total,
        note=note,
        created_by_user_id=ctx.user.id,
    )
    db.add(row)
    if bump_lead_score:
        # 轻量联动：平均分 * 20（最高 100）
        suggested = int(min(100, max(0, total * 20)))
        if lead.lead_score is None or suggested > lead.lead_score:
            lead.lead_score = suggested
    db.commit()
    db.refresh(row)
    return row


def deal_suggestions_from_bant(bant: BantEvaluation | None) -> dict:
    """转化建商机时的可选建议字段。"""
    if bant is None:
        return {}
    authority_map = {5: "决策者", 4: "决策者", 3: "影响者", 2: "评估者", 1: "使用者"}
    days = max(7, (6 - int(bant.time_score)) * 14)
    note = (bant.note or "").strip()
    desc_parts = [f"BANT需求评分 {bant.need_score}/5"]
    if note:
        desc_parts.append(note)
    return {
        "amount": float(int(bant.budget_score) * 20000),
        "expected_close_date": date.today() + timedelta(days=days),
        "description": "；".join(desc_parts),
        "contact_role": authority_map.get(int(bant.authority_score), "影响者"),
    }


def require_evaluation(db: Session, tenant_id: UUID, eval_id: UUID) -> BantEvaluation:
    row = (
        db.query(BantEvaluation)
        .filter(uuid_eq(BantEvaluation.id, eval_id), BantEvaluation.tenant_id == tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="BANT 评估不存在")
    return row
