"""线索/客户漏斗与销售看板。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import CrmTask, Customer, Deal, Lead


def source_roi_report(
    db: Session,
    ctx: TenantContext,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict:
    """按来源汇总线索量、转化率、平均转化周期、CPL。"""
    q = db.query(Lead).filter(Lead.tenant_id == ctx.tenant_id, Lead.deleted_at.is_(None))
    if start_date is not None:
        q = q.filter(Lead.created_at >= start_date)
    if end_date is not None:
        q = q.filter(Lead.created_at < end_date)
    leads = q.all()
    buckets: dict[str, dict] = {}
    for lead in leads:
        key = lead.source or "未填写"
        bucket = buckets.setdefault(
            key,
            {
                "source": key,
                "leads": 0,
                "converted": 0,
                "total_cost": 0.0,
                "cycle_days_sum": 0.0,
                "cycle_samples": 0,
                "utm_campaigns": set(),
            },
        )
        bucket["leads"] += 1
        if lead.acquisition_cost is not None:
            bucket["total_cost"] += float(lead.acquisition_cost)
        if lead.utm_campaign:
            bucket["utm_campaigns"].add(lead.utm_campaign)
        if lead.status == "已转化" and lead.converted_customer_id:
            bucket["converted"] += 1
            # 转化周期：用 updated_at 近似（转化时更新）
            if lead.created_at and lead.updated_at:
                delta = (lead.updated_at - lead.created_at).total_seconds() / 86400
                if delta >= 0:
                    bucket["cycle_days_sum"] += delta
                    bucket["cycle_samples"] += 1

    rows = []
    for bucket in buckets.values():
        leads_n = bucket["leads"]
        conv_n = bucket["converted"]
        cost = bucket["total_cost"]
        samples = bucket["cycle_samples"]
        rows.append(
            {
                "source": bucket["source"],
                "leads": leads_n,
                "converted": conv_n,
                "conversion_rate": round(conv_n / leads_n * 100, 1) if leads_n else 0.0,
                "avg_cycle_days": round(bucket["cycle_days_sum"] / samples, 1) if samples else None,
                "total_cost": round(cost, 2),
                "cpl": round(cost / leads_n, 2) if leads_n and cost else None,
                "cpa": round(cost / conv_n, 2) if conv_n and cost else None,
                "utm_campaigns": sorted(bucket["utm_campaigns"]),
            }
        )
    rows.sort(key=lambda r: r["leads"], reverse=True)
    return {"items": rows, "total_leads": len(leads)}


def lead_customer_funnel_report(
    db: Session,
    ctx: TenantContext,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict:
    lead_q = db.query(Lead).filter(Lead.tenant_id == ctx.tenant_id, Lead.deleted_at.is_(None))
    cust_q = db.query(Customer).filter(Customer.tenant_id == ctx.tenant_id, Customer.deleted_at.is_(None))
    deal_q = db.query(Deal).filter(Deal.tenant_id == ctx.tenant_id, Deal.deleted_at.is_(None))
    if start_date is not None:
        lead_q = lead_q.filter(Lead.created_at >= start_date)
        cust_q = cust_q.filter(Customer.created_at >= start_date)
        deal_q = deal_q.filter(Deal.created_at >= start_date)
    if end_date is not None:
        lead_q = lead_q.filter(Lead.created_at < end_date)
        cust_q = cust_q.filter(Customer.created_at < end_date)
        deal_q = deal_q.filter(Deal.created_at < end_date)

    total_leads = lead_q.count()

    status_q = db.query(Lead.status, func.count(Lead.id)).filter(
        Lead.tenant_id == ctx.tenant_id, Lead.deleted_at.is_(None)
    )
    if start_date is not None:
        status_q = status_q.filter(Lead.created_at >= start_date)
    if end_date is not None:
        status_q = status_q.filter(Lead.created_at < end_date)
    by_status = {str(s or "未知"): int(c) for s, c in status_q.group_by(Lead.status).all()}

    converted = by_status.get("已转化", 0)
    customers = cust_q.count()
    open_deals = deal_q.filter(Deal.status == "open").count()
    won_deals = deal_q.filter(Deal.status == "won").count()

    source_q = db.query(Lead.source, func.count(Lead.id)).filter(
        Lead.tenant_id == ctx.tenant_id, Lead.deleted_at.is_(None)
    )
    if start_date is not None:
        source_q = source_q.filter(Lead.created_at >= start_date)
    if end_date is not None:
        source_q = source_q.filter(Lead.created_at < end_date)
    by_source = []
    for src, cnt in source_q.group_by(Lead.source).all():
        conv_q = db.query(func.count(Lead.id)).filter(
            Lead.tenant_id == ctx.tenant_id,
            Lead.deleted_at.is_(None),
            Lead.status == "已转化",
        )
        if src is None:
            conv_q = conv_q.filter(Lead.source.is_(None))
        else:
            conv_q = conv_q.filter(Lead.source == src)
        if start_date is not None:
            conv_q = conv_q.filter(Lead.created_at >= start_date)
        if end_date is not None:
            conv_q = conv_q.filter(Lead.created_at < end_date)
        conv_cnt = int(conv_q.scalar() or 0)
        by_source.append(
            {
                "source": src or "未填写",
                "leads": int(cnt),
                "converted": conv_cnt,
                "conversion_rate": round(conv_cnt / cnt * 100, 1) if cnt else 0.0,
            }
        )

    stages = [
        {"key": "leads", "label": "线索", "count": total_leads},
        {"key": "converted", "label": "已转化线索", "count": converted},
        {"key": "customers", "label": "客户", "count": customers},
        {"key": "open_deals", "label": "进行中商机", "count": open_deals},
        {"key": "won_deals", "label": "赢单商机", "count": won_deals},
    ]
    return {
        "stages": stages,
        "by_status": by_status,
        "by_source": by_source,
        "lead_to_customer_rate": round(converted / total_leads * 100, 1) if total_leads else 0.0,
    }


def sales_board_report(db: Session, ctx: TenantContext) -> dict:
    uid = ctx.user.id
    open_leads = (
        db.query(func.count(Lead.id))
        .filter(
            Lead.tenant_id == ctx.tenant_id,
            Lead.deleted_at.is_(None),
            Lead.owner_user_id == uid,
            Lead.status != "已转化",
        )
        .scalar()
        or 0
    )
    open_deals = (
        db.query(func.count(Deal.id))
        .filter(
            Deal.tenant_id == ctx.tenant_id,
            Deal.deleted_at.is_(None),
            Deal.owner_user_id == uid,
            Deal.status == "open",
        )
        .scalar()
        or 0
    )
    won_amount = (
        db.query(func.coalesce(func.sum(Deal.amount), 0))
        .filter(
            Deal.tenant_id == ctx.tenant_id,
            Deal.deleted_at.is_(None),
            Deal.owner_user_id == uid,
            Deal.status == "won",
        )
        .scalar()
        or 0
    )
    open_tasks = (
        db.query(func.count(CrmTask.id))
        .filter(
            CrmTask.tenant_id == ctx.tenant_id,
            CrmTask.deleted_at.is_(None),
            CrmTask.owner_user_id == uid,
            CrmTask.status.in_(("open", "in_progress")),
        )
        .scalar()
        or 0
    )
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    new_leads_7d = (
        db.query(func.count(Lead.id))
        .filter(
            Lead.tenant_id == ctx.tenant_id,
            Lead.deleted_at.is_(None),
            Lead.owner_user_id == uid,
            Lead.created_at >= week_ago,
        )
        .scalar()
        or 0
    )
    return {
        "owner_user_id": str(uid),
        "open_leads": int(open_leads),
        "open_deals": int(open_deals),
        "won_amount": float(won_amount),
        "open_tasks": int(open_tasks),
        "new_leads_7d": int(new_leads_7d),
    }
