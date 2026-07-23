"""客户生命周期报表。"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import Customer
from app.services.crm.crm_scope_service import apply_customer_list_scope


def calculate_lifecycle(customer: Customer, *, today: date | None = None) -> str:
    today = today or date.today()
    if not customer.last_deal_date:
        return "潜在"
    days = (today - customer.last_deal_date).days
    if days <= 30:
        return "新客户"
    if days <= 90:
        return "活跃客户"
    if days <= 180:
        return "沉睡客户"
    return "流失客户"


def lifecycle_report(db: Session, ctx: TenantContext) -> dict:
    """客户生命周期分桶（受客户可见范围约束）。"""
    q = db.query(Customer).filter(Customer.tenant_id == ctx.tenant_id, Customer.deleted_at.is_(None))
    q = apply_customer_list_scope(q, ctx, db)
    customers = q.all()
    buckets = {"潜在": 0, "新客户": 0, "活跃客户": 0, "沉睡客户": 0, "流失客户": 0}
    samples: dict[str, list[dict]] = {k: [] for k in buckets}
    today = date.today()
    for c in customers:
        stage = calculate_lifecycle(c, today=today)
        buckets[stage] = buckets.get(stage, 0) + 1
        if len(samples[stage]) < 5:
            samples[stage].append(
                {
                    "id": str(c.id),
                    "company_name": c.company_name,
                    "last_deal_date": str(c.last_deal_date) if c.last_deal_date else None,
                    "total_revenue": float(c.total_revenue or 0),
                }
            )
    return {
        "as_of": str(today),
        "total": len(customers),
        "buckets": buckets,
        "samples": samples,
    }
