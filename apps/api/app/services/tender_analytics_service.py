"""招标线索效果看板（FR-TENDER-09）。"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import Deal, Lead
from app.models.tender import ScoredTenderLead
from app.schemas.tender_leads import TenderAnalyticsOut


def _pct(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round(100.0 * num / den, 1)


def get_tender_analytics(db: Session, ctx: TenantContext) -> TenderAnalyticsOut:
    rows = (
        db.query(ScoredTenderLead)
        .filter(ScoredTenderLead.tenant_id == ctx.tenant_id)
        .all()
    )
    total = len(rows)
    claimed = [r for r in rows if r.status == "valid" and r.converted_lead_id]
    handled = [r for r in rows if r.status != "pending"]
    high = [r for r in rows if int(r.match_score or 0) >= 60]
    bad = [r for r in rows if r.status in ("invalid", "expired")]

    lead_ids = [r.converted_lead_id for r in claimed if r.converted_lead_id]
    deal_lead_ids: set = set()
    if lead_ids:
        deals = (
            db.query(Deal.converted_from_lead_id)
            .filter(
                Deal.tenant_id == ctx.tenant_id,
                Deal.deleted_at.is_(None),
                Deal.converted_from_lead_id.in_(lead_ids),
            )
            .all()
        )
        deal_lead_ids = {d[0] for d in deals if d[0]}
        # 兜底：线索已转客户，且该客户下有商机
        leads = (
            db.query(Lead)
            .filter(Lead.tenant_id == ctx.tenant_id, Lead.id.in_(lead_ids))
            .all()
        )
        cust_ids = [L.converted_customer_id for L in leads if L.converted_customer_id]
        if cust_ids:
            for L in leads:
                if L.id in deal_lead_ids:
                    continue
                if not L.converted_customer_id:
                    continue
                exists = (
                    db.query(Deal.id)
                    .filter(
                        Deal.tenant_id == ctx.tenant_id,
                        Deal.deleted_at.is_(None),
                        Deal.customer_id == L.converted_customer_id,
                    )
                    .first()
                )
                if exists:
                    deal_lead_ids.add(L.id)

    converted_n = len(deal_lead_ids)

    buckets_def = [
        ("0-20", 0, 20),
        ("21-40", 21, 40),
        ("41-60", 41, 60),
        ("61-80", 61, 80),
        ("81-100", 81, 100),
    ]
    score_buckets = []
    for label, lo, hi in buckets_def:
        cnt = sum(1 for r in rows if lo <= int(r.match_score or 0) <= hi)
        score_buckets.append({"bucket": label, "count": cnt})

    # 近 8 周推送量 + 当周 claim 转 Deal（近似）
    now = datetime.now(timezone.utc)
    weekly: dict[str, dict] = defaultdict(lambda: {"week": "", "pushed": 0, "claimed": 0, "converted": 0})
    for i in range(7, -1, -1):
        start = (now - timedelta(days=now.weekday() + 7 * i)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        key = start.date().isoformat()
        weekly[key]["week"] = key

    for r in rows:
        created = r.created_at
        if created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        week_start = (created - timedelta(days=created.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        key = week_start.date().isoformat()
        if key not in weekly:
            continue
        weekly[key]["pushed"] += 1
        if r.status == "valid" and r.converted_lead_id:
            weekly[key]["claimed"] += 1
            if r.converted_lead_id in deal_lead_ids:
                weekly[key]["converted"] += 1

    trend = []
    for key in sorted(weekly.keys()):
        w = weekly[key]
        pushed = w["pushed"]
        trend.append(
            {
                "week": w["week"],
                "pushed": pushed,
                "claimed": w["claimed"],
                "converted": w["converted"],
                "conversion_rate": _pct(w["converted"], pushed),
            }
        )

    return TenderAnalyticsOut(
        total_pushed=total,
        claimed_count=len(claimed),
        follow_rate=_pct(len(handled), total),
        converted_to_deal_count=converted_n,
        conversion_rate=_pct(converted_n, total),
        high_match_count=len(high),
        high_match_rate=_pct(len(high), total),
        invalid_expired_count=len(bad),
        invalid_expired_rate=_pct(len(bad), total),
        score_buckets=score_buckets,
        weekly_trend=trend,
    )
