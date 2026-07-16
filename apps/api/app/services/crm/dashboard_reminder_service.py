"""工作台 CRM 提醒计数（v1.2 FR-PAY-04 / FR-CONTRACT-04）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import Contract, PaymentPlan
from app.services.crm.payment_service import list_receivables


def dashboard_crm_reminders(db: Session, ctx: TenantContext) -> dict[str, int]:
    """返回 payment_due_7d / payment_overdue / contract_expiring_30d。"""
    now = datetime.now(timezone.utc)
    today = now.date()
    due_end = today + timedelta(days=7)
    contract_end = today + timedelta(days=30)

    recv = list_receivables(db, ctx)
    payment_due_7d = 0
    payment_overdue = 0
    plan_ids = [item.plan_id for item in recv.items if item.plan_id]
    plans = {
        p.id: p
        for p in db.query(PaymentPlan)
        .filter(PaymentPlan.tenant_id == ctx.tenant_id, PaymentPlan.id.in_(plan_ids))
        .all()
    } if plan_ids else {}

    for item in recv.items:
        days = int(item.days_overdue or 0)
        if days > 0:
            payment_overdue += 1
            continue
        plan = plans.get(item.plan_id)
        if not plan or plan.plan_date is None:
            continue
        pdt = plan.plan_date
        if pdt.tzinfo is None:
            pdt = pdt.replace(tzinfo=timezone.utc)
        if today <= pdt.date() <= due_end:
            payment_due_7d += 1

    contract_expiring_30d = 0
    rows = (
        db.query(Contract)
        .filter(
            Contract.tenant_id == ctx.tenant_id,
            Contract.deleted_at.is_(None),
            Contract.end_date.isnot(None),
            Contract.status.notin_(("cancelled", "terminated", "void", "draft", "expired")),
        )
        .all()
    )
    for c in rows:
        edt = c.end_date
        if edt is None:
            continue
        if edt.tzinfo is None:
            edt = edt.replace(tzinfo=timezone.utc)
        d = edt.date()
        if today <= d <= contract_end:
            contract_expiring_30d += 1

    return {
        "payment_due_7d": payment_due_7d,
        "payment_overdue": payment_overdue,
        "contract_expiring_30d": contract_expiring_30d,
    }
