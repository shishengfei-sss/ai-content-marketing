"""公海自动回收：将超时未跟进的认领线索/客户退回公海。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.crm import Customer, CustomerPool, Lead, LeadPool

logger = logging.getLogger(__name__)


def process_auto_reclaim(db: Session, *, batch_per_pool: int = 50) -> dict[str, int]:
    """按各公海 auto_reclaim_days 扫描并回收。返回计数。"""
    now = datetime.now(timezone.utc)
    lead_n = 0
    customer_n = 0

    lead_pools = (
        db.query(LeadPool)
        .filter(LeadPool.auto_reclaim_days.isnot(None), LeadPool.auto_reclaim_days > 0)
        .all()
    )
    for pool in lead_pools:
        cutoff = now - timedelta(days=int(pool.auto_reclaim_days))
        leads = (
            db.query(Lead)
            .filter(
                Lead.tenant_id == pool.tenant_id,
                Lead.deleted_at.is_(None),
                Lead.status != "已转化",
                Lead.pool_id.is_(None),
                Lead.claimed_at.isnot(None),
                Lead.claimed_at < cutoff,
            )
            .order_by(Lead.claimed_at.asc())
            .limit(batch_per_pool)
            .all()
        )
        for lead in leads:
            lead.pool_id = pool.id
            lead.owner_user_id = None
            lead.claimed_at = None
            lead_n += 1
        if leads:
            db.commit()

    cust_pools = (
        db.query(CustomerPool)
        .filter(CustomerPool.auto_reclaim_days.isnot(None), CustomerPool.auto_reclaim_days > 0)
        .all()
    )
    for pool in cust_pools:
        cutoff = now - timedelta(days=int(pool.auto_reclaim_days))
        customers = (
            db.query(Customer)
            .filter(
                Customer.tenant_id == pool.tenant_id,
                Customer.deleted_at.is_(None),
                Customer.pool_id.is_(None),
                Customer.claimed_at.isnot(None),
                Customer.claimed_at < cutoff,
            )
            .order_by(Customer.claimed_at.asc())
            .limit(batch_per_pool)
            .all()
        )
        for cust in customers:
            cust.pool_id = pool.id
            cust.owner_user_id = None
            cust.claimed_at = None
            customer_n += 1
        if customers:
            db.commit()

    if lead_n or customer_n:
        logger.info("Auto-reclaim: leads=%s customers=%s", lead_n, customer_n)
    return {"leads": lead_n, "customers": customer_n}
