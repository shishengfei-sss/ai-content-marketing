"""交易报表（v1.2 FR-DR-04～07 / FR-CRM-OPS-01）。"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models import User
from app.models.crm import Deal, Order, Payment
from app.services.crm.payment_service import list_receivables


def _order_path(order: Order) -> str:
    """四路径：deal_direct / via_quote / via_contract / via_quote_contract。"""
    has_q = bool(order.quote_id)
    has_c = bool(order.contract_id)
    if has_q and has_c:
        return "via_quote_contract"
    if has_c:
        return "via_contract"
    if has_q:
        return "via_quote"
    return "deal_direct"


def trade_report(
    db: Session,
    ctx: TenantContext,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict:
    tenant_id = ctx.tenant_id

    deals_q = db.query(Deal).filter(Deal.tenant_id == tenant_id, Deal.deleted_at.is_(None))
    if start_date:
        deals_q = deals_q.filter(Deal.created_at >= start_date)
    if end_date:
        deals_q = deals_q.filter(Deal.created_at < end_date)
    deal_total = deals_q.count()
    won_deals = deals_q.filter(Deal.status == "won").count()

    orders_q = db.query(Order).filter(
        Order.tenant_id == tenant_id,
        Order.deleted_at.is_(None),
        Order.status.notin_(("draft", "cancelled", "superseded")),
    )
    if start_date:
        orders_q = orders_q.filter(Order.created_at >= start_date)
    if end_date:
        orders_q = orders_q.filter(Order.created_at < end_date)
    orders = orders_q.all()

    path_counts: dict[str, int] = defaultdict(int)
    path_amount: dict[str, float] = defaultdict(float)
    order_amount_total = 0.0
    for o in orders:
        path = _order_path(o)
        amt = float(o.amount or 0)
        path_counts[path] += 1
        path_amount[path] += amt
        order_amount_total += amt

    path_labels = {
        "deal_direct": "商机直转订单",
        "via_quote": "经报价",
        "via_contract": "经合同",
        "via_quote_contract": "报价+合同",
    }
    paths = [
        {
            "code": code,
            "label": path_labels[code],
            "count": path_counts.get(code, 0),
            "amount": round(path_amount.get(code, 0.0), 2),
            "share_pct": round(path_counts.get(code, 0) / len(orders) * 100, 1) if orders else 0.0,
        }
        for code in path_labels
    ]

    deal_to_order_rate = round(len(orders) / deal_total * 100, 1) if deal_total else 0.0
    won_to_order_rate = round(len(orders) / won_deals * 100, 1) if won_deals else 0.0

    order_ids = [o.id for o in orders]
    paid_total = 0.0
    paid_by_order: dict[UUID, float] = {oid: 0.0 for oid in order_ids}
    if order_ids:
        pays = (
            db.query(Payment)
            .filter(
                Payment.tenant_id == tenant_id,
                Payment.order_id.in_(order_ids),
                Payment.deleted_at.is_(None),
                Payment.status == "confirmed",
            )
            .all()
        )
        for p in pays:
            amt = float(p.amount or 0)
            paid_total += amt
            paid_by_order[p.order_id] = paid_by_order.get(p.order_id, 0.0) + amt

    payment_rate = round(paid_total / order_amount_total * 100, 1) if order_amount_total else 0.0

    recv = list_receivables(db, ctx)

    # 负责人业绩：成交订单金额 + 订单数 + 回款率
    owner_agg: dict[UUID, dict] = {}
    for o in orders:
        oid = o.owner_user_id
        row = owner_agg.setdefault(
            oid,
            {"owner_user_id": str(oid), "order_count": 0, "order_amount": 0.0, "paid_amount": 0.0},
        )
        row["order_count"] += 1
        row["order_amount"] += float(o.amount or 0)
        row["paid_amount"] += paid_by_order.get(o.id, 0.0)

    won_by_owner = (
        db.query(Deal.owner_user_id, func.count(Deal.id))
        .filter(Deal.tenant_id == tenant_id, Deal.deleted_at.is_(None), Deal.status == "won")
        .group_by(Deal.owner_user_id)
        .all()
    )
    won_map = {uid: cnt for uid, cnt in won_by_owner}

    user_ids = set(owner_agg.keys()) | {uid for uid, _ in won_by_owner}
    users = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}

    owners = []
    for uid, row in owner_agg.items():
        u = users.get(uid)
        oa = row["order_amount"]
        owners.append(
            {
                "owner_user_id": row["owner_user_id"],
                "owner_name": (u.display_name or u.phone or str(uid)[:8]) if u else str(uid)[:8],
                "order_count": row["order_count"],
                "order_amount": round(oa, 2),
                "paid_amount": round(row["paid_amount"], 2),
                "payment_rate": round(row["paid_amount"] / oa * 100, 1) if oa else 0.0,
                "won_deal_count": int(won_map.get(uid, 0)),
            }
        )
    for uid, cnt in won_map.items():
        if uid in owner_agg:
            continue
        u = users.get(uid)
        owners.append(
            {
                "owner_user_id": str(uid),
                "owner_name": (u.display_name or u.phone or str(uid)[:8]) if u else str(uid)[:8],
                "order_count": 0,
                "order_amount": 0.0,
                "paid_amount": 0.0,
                "payment_rate": 0.0,
                "won_deal_count": int(cnt),
            }
        )
    owners.sort(key=lambda r: (r["order_amount"], r["won_deal_count"]), reverse=True)

    return {
        "deal_total": deal_total,
        "won_deal_count": won_deals,
        "order_count": len(orders),
        "order_amount": round(order_amount_total, 2),
        "deal_to_order_rate": deal_to_order_rate,
        "won_to_order_rate": won_to_order_rate,
        "paths": paths,
        "payment_rate": payment_rate,
        "paid_amount": round(paid_total, 2),
        "aging": {
            "buckets": recv.buckets,
            "total_outstanding": recv.total_outstanding,
            "item_count": len(recv.items),
        },
        "owners": owners[:20],
    }
