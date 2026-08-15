"""P05 清结算。对照 PRD 06#p05 · #p05a · #p05b · #p05c · §8.14.3 · F10。"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from app.models import Tenant, User
from app.models.shop import (
    ShopMerchantAccount,
    ShopOnboardingApplication,
    ShopOrder,
    ShopPlatformCategory,
    ShopProduct,
    ShopRefund,
    ShopSettlementBatch,
    ShopSettlementItem,
    ShopStore,
)
from app.services.shop.entitlement_service import TZ_SH
from app.services.shop.platform_number_service import generate_platform_number

SETTLEMENT_DELAY_DAYS = 7
PAID_ORDER_STATUSES = ("paid", "claim_pending")
STATUS_LABEL = {
    "pending": "待结算",
    "paid": "已打款",
    "payment_failed": "打款失败",
    "closed": "已关账",
    "carried_forward": "结转中",
    "offset_settled": "已抵扣",
}
ITEM_TYPE_LABEL = {
    "order_income": "订单收入",
    "refund_reversal": "退款冲正",
    "period_carry_in": "上期结转",
    "adjustment": "调账",
}
TODO_STATUSES = ("pending", "payment_failed")


def _now() -> datetime:
    return datetime.now(TZ_SH)


def iso_week_bounds(d: date) -> tuple[date, date]:
    iso = d.isocalendar()
    return date.fromisocalendar(iso[0], iso[1], 1), date.fromisocalendar(iso[0], iso[1], 7)


def last_completed_week_end(as_of: date) -> date:
    start, end = iso_week_bounds(as_of)
    if as_of >= end:
        return end
    prev = start - timedelta(days=1)
    return iso_week_bounds(prev)[1]


def _payout_account(db: Session, tenant_id: UUID) -> dict:
    app = (
        db.query(ShopOnboardingApplication)
        .filter(or_(
            cast(ShopOnboardingApplication.tenant_id, String) == str(tenant_id),
            cast(ShopOnboardingApplication.tenant_id, String) == tenant_id.hex,
        ))
        .order_by(ShopOnboardingApplication.submitted_at.desc())
        .first()
    )
    info = dict((app.bank_account_info if app else None) or {})
    account_no = str(info.get("account_no") or info.get("bank_account") or info.get("account") or "").strip()
    bank_name = str(info.get("bank_name") or info.get("bank") or "").strip()
    account_name = str(info.get("account_name") or info.get("name") or "").strip()
    last4 = account_no[-4:] if len(account_no) >= 4 else ""
    valid = len(account_no) >= 4
    return {
        "valid": valid,
        "account_no": account_no,
        "bank_name": bank_name,
        "account_name": account_name,
        "last4": last4,
        "label": (f"对公尾号 {last4}" + (f" · 开户行 {bank_name}" if bank_name else "")) if valid else "",
    }


def _fee_cents(db: Session, product: ShopProduct | None, amount: int) -> int:
    if not product or not product.category_id or amount <= 0:
        return 0
    cat = db.get(ShopPlatformCategory, product.category_id)
    bps = int(cat.platform_fee_bps or 0) if cat else 0
    return amount * bps // 10000


def _existing_batch(db: Session, tenant_id: UUID, shop_id: UUID, period_end: date) -> ShopSettlementBatch | None:
    return (
        db.query(ShopSettlementBatch)
        .filter(
            ShopSettlementBatch.period_end == period_end,
        )
        .filter(
            or_(
                cast(ShopSettlementBatch.tenant_id, String) == str(tenant_id),
                cast(ShopSettlementBatch.tenant_id, String) == tenant_id.hex,
            )
        )
        .filter(
            or_(
                cast(ShopSettlementBatch.shop_id, String) == str(shop_id),
                cast(ShopSettlementBatch.shop_id, String) == shop_id.hex,
            )
        )
        .first()
    )


def _refunded_order_ids(db: Session) -> set[str]:
    rows = (
        db.query(ShopRefund.order_id)
        .filter(ShopRefund.status == "succeeded")
        .all()
    )
    return {str(r[0]) for r in rows if r[0]}


def _batched_refund_ids(db: Session) -> set[str]:
    rows = (
        db.query(ShopSettlementItem.refund_id)
        .filter(ShopSettlementItem.refund_id.isnot(None))
        .all()
    )
    return {str(r[0]) for r in rows if r[0]}


def close_period(
    db: Session,
    *,
    period_end: date | None = None,
    as_of: date | None = None,
    delay_days: int = SETTLEMENT_DELAY_DAYS,
) -> dict:
    """F10 周关账：每 tenant+shop 出 1 条批次。"""
    as_of = as_of or _now().date()
    week_end = period_end or last_completed_week_end(as_of)
    week_start, week_end = iso_week_bounds(week_end)
    closed_at = datetime.combine(week_end, datetime.min.time(), tzinfo=TZ_SH) + timedelta(days=1)
    delay_cut = datetime.combine(as_of, datetime.min.time(), tzinfo=TZ_SH) - timedelta(days=delay_days)

    refunded_orders = _refunded_order_ids(db)
    batched_refunds = _batched_refund_ids(db)

    orders = (
        db.query(ShopOrder)
        .filter(
            ShopOrder.status.in_(PAID_ORDER_STATUSES),
            ShopOrder.paid_at.isnot(None),
            ShopOrder.settled_at.is_(None),
        )
        .all()
    )
    eligible: list[ShopOrder] = []
    for o in orders:
        if str(o.id) in refunded_orders:
            continue
        paid_at = o.paid_at
        if paid_at.tzinfo is None:
            paid_at = paid_at.replace(tzinfo=timezone.utc)
        if paid_at > delay_cut:
            continue
        merchant = (
            db.query(ShopMerchantAccount)
            .filter(
                or_(
                    cast(ShopMerchantAccount.tenant_id, String) == str(o.tenant_id),
                    cast(ShopMerchantAccount.tenant_id, String) == o.tenant_id.hex,
                )
            )
            .first()
        )
        if merchant and merchant.status == "closed":
            continue
        eligible.append(o)

    grouped: dict[tuple, list[ShopOrder]] = defaultdict(list)
    for o in eligible:
        grouped[(str(o.tenant_id), str(o.shop_id))].append(o)

    carry_rows = (
        db.query(ShopSettlementBatch)
        .filter(ShopSettlementBatch.status == "carried_forward")
        .all()
    )
    for b in carry_rows:
        key = (str(b.tenant_id), str(b.shop_id))
        grouped.setdefault(key, [])

    refunds = (
        db.query(ShopRefund)
        .filter(ShopRefund.status == "succeeded")
        .all()
    )
    refund_by_shop: dict[tuple, list[ShopRefund]] = defaultdict(list)
    for rf in refunds:
        if str(rf.id) in batched_refunds:
            continue
        order = db.get(ShopOrder, rf.order_id)
        if not order or order.settled_at is None:
            continue
        key = (str(order.tenant_id), str(order.shop_id))
        refund_by_shop[key].append(rf)
        grouped.setdefault(key, [])

    created = 0
    skipped = 0
    for (tid, sid), order_list in grouped.items():
        tenant_id = UUID(tid)
        shop_id = UUID(sid)
        if _existing_batch(db, tenant_id, shop_id, week_end):
            skipped += 1
            continue
        _build_batch(
            db,
            tenant_id=tenant_id,
            shop_id=shop_id,
            period_start=week_start,
            period_end=week_end,
            orders=order_list,
            refunds=refund_by_shop.get((tid, sid), []),
            closed_at=closed_at,
        )
        created += 1
    db.commit()
    return {
        "period_start": week_start.isoformat(),
        "period_end": week_end.isoformat(),
        "created": created,
        "skipped": skipped,
    }


def _build_batch(
    db: Session,
    *,
    tenant_id: UUID,
    shop_id: UUID,
    period_start: date,
    period_end: date,
    orders: list[ShopOrder],
    refunds: list[ShopRefund],
    closed_at: datetime,
) -> ShopSettlementBatch:
    carry_src = (
        db.query(ShopSettlementBatch)
        .filter(
            ShopSettlementBatch.status == "carried_forward",
            or_(
                cast(ShopSettlementBatch.tenant_id, String) == str(tenant_id),
                cast(ShopSettlementBatch.tenant_id, String) == tenant_id.hex,
            ),
            or_(
                cast(ShopSettlementBatch.shop_id, String) == str(shop_id),
                cast(ShopSettlementBatch.shop_id, String) == shop_id.hex,
            ),
        )
        .all()
    )
    opening = sum(int(b.net_amount_cents or 0) for b in carry_src)
    if opening > 0:
        opening = 0

    gross = 0
    fee_total = 0
    items: list[ShopSettlementItem] = []
    for o in orders:
        amt = int(o.paid_amount_cents or o.amount_cents or 0)
        product = db.get(ShopProduct, o.product_id)
        fee = _fee_cents(db, product, amt)
        gross += amt
        fee_total += fee
        items.append(
            ShopSettlementItem(
                id=uuid4(),
                item_type="order_income",
                order_id=o.id,
                amount_cents=amt,
                fee_cents=fee,
            )
        )
        o.settled_at = closed_at

    reversal = 0
    for rf in refunds:
        amt = int(rf.amount_cents or 0)
        reversal += amt
        items.append(
            ShopSettlementItem(
                id=uuid4(),
                item_type="refund_reversal",
                order_id=rf.order_id,
                refund_id=rf.id,
                amount_cents=-amt,
                fee_cents=0,
            )
        )

    for src in carry_src:
        items.append(
            ShopSettlementItem(
                id=uuid4(),
                item_type="period_carry_in",
                source_batch_id=src.id,
                amount_cents=int(src.net_amount_cents or 0),
                fee_cents=0,
                note=src.batch_no,
            )
        )

    period_net = gross - fee_total - reversal
    net = period_net + opening
    if net > 0:
        st = "pending"
    elif net == 0:
        st = "closed"
    else:
        st = "carried_forward"

    batch = ShopSettlementBatch(
        id=uuid4(),
        tenant_id=tenant_id,
        shop_id=shop_id,
        batch_no=generate_platform_number(db, "settlement_batch"),
        period_start=period_start,
        period_end=period_end,
        gross_amount_cents=gross,
        platform_fee_cents=fee_total,
        refund_reversal_cents=reversal,
        opening_balance_cents=opening,
        period_net_cents=period_net,
        net_amount_cents=net,
        status=st,
    )
    db.add(batch)
    db.flush()
    for it in items:
        it.batch_id = batch.id
        db.add(it)
    return batch


def _merchant_map(db: Session) -> dict[str, ShopMerchantAccount]:
    out = {}
    for m in db.query(ShopMerchantAccount).all():
        out[str(m.tenant_id)] = m
        out[m.tenant_id.hex] = m
    return out


def _batch_out(db: Session, b: ShopSettlementBatch, merchants: dict | None = None) -> dict:
    merchants = merchants or _merchant_map(db)
    m = merchants.get(str(b.tenant_id)) or merchants.get(getattr(b.tenant_id, "hex", ""))
    tenant = db.get(Tenant, b.tenant_id)
    shop = db.get(ShopStore, b.shop_id)
    name = (m.display_name if m else None) or (tenant.name if tenant else "")
    offset_no = None
    if b.offset_by_batch_id:
        src = db.get(ShopSettlementBatch, b.offset_by_batch_id)
        offset_no = src.batch_no if src else None
    op_name = None
    if b.operator_id:
        user = db.get(User, b.operator_id)
        op_name = (user.display_name if user else None) or (user.phone if user else None)
    acct = _payout_account(db, b.tenant_id)
    return {
        "id": str(b.id),
        "batch_no": b.batch_no,
        "tenant_id": str(b.tenant_id),
        "shop_id": str(b.shop_id),
        "shop_name": shop.name if shop else None,
        "merchant_name": name,
        "merchant_no": m.merchant_no if m else None,
        "period_start": b.period_start.isoformat() if b.period_start else None,
        "period_end": b.period_end.isoformat() if b.period_end else None,
        "gross_amount_cents": int(b.gross_amount_cents or 0),
        "platform_fee_cents": int(b.platform_fee_cents or 0),
        "refund_reversal_cents": int(b.refund_reversal_cents or 0),
        "opening_balance_cents": int(b.opening_balance_cents or 0),
        "period_net_cents": int(b.period_net_cents or 0),
        "net_amount_cents": int(b.net_amount_cents or 0),
        "generated_at": b.created_at.isoformat() if b.created_at else None,
        "status": b.status,
        "status_label": STATUS_LABEL.get(b.status, b.status),
        "paid_at": b.paid_at.isoformat() if b.paid_at else None,
        "operator_id": str(b.operator_id) if b.operator_id else None,
        "operator_name": op_name,
        "fail_reason": b.fail_reason,
        "confirm_remark": b.confirm_remark,
        "transfer_voucher_url": b.transfer_voucher_url,
        "offset_by_batch_id": str(b.offset_by_batch_id) if b.offset_by_batch_id else None,
        "offset_by_batch_no": offset_no,
        "offset_settled_at": b.offset_settled_at.isoformat() if b.offset_settled_at else None,
        "payout_account": acct,
    }


def list_batches(
    db: Session,
    *,
    q: str | None = None,
    status: str | None = None,
    view: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str | None = None,
    sort_dir: str = "desc",
) -> dict:
    query = db.query(ShopSettlementBatch)
    if view == "todo" or status == "todo":
        query = query.filter(ShopSettlementBatch.status.in_(TODO_STATUSES))
    elif status:
        query = query.filter(ShopSettlementBatch.status == status)
    if period_start:
        try:
            query = query.filter(
                ShopSettlementBatch.period_start >= date.fromisoformat(period_start[:10])
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="周期日期无效") from exc
    if period_end:
        try:
            query = query.filter(
                ShopSettlementBatch.period_end <= date.fromisoformat(period_end[:10])
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="周期日期无效") from exc
    if q:
        needle = f"%{q.strip()}%"
        mids = [
            m.tenant_id
            for m in db.query(ShopMerchantAccount)
            .filter(
                or_(
                    ShopMerchantAccount.display_name.ilike(needle),
                    ShopMerchantAccount.legal_name.ilike(needle),
                    ShopMerchantAccount.merchant_no.ilike(needle),
                )
            )
            .all()
        ]
        tnames = [t.id for t in db.query(Tenant).filter(Tenant.name.ilike(needle)).all()]
        ids = list({*mids, *tnames})
        clauses = [ShopSettlementBatch.batch_no.ilike(needle)]
        for tid in ids:
            clauses.append(
                or_(
                    cast(ShopSettlementBatch.tenant_id, String) == str(tid),
                    cast(ShopSettlementBatch.tenant_id, String) == tid.hex,
                )
            )
        query = query.filter(or_(*clauses))

    sort_map = {
        "batch_no": ShopSettlementBatch.batch_no,
        "gross_amount_cents": ShopSettlementBatch.gross_amount_cents,
        "generated_at": ShopSettlementBatch.created_at,
        "created_at": ShopSettlementBatch.created_at,
    }
    col = sort_map.get(sort_by or "created_at", ShopSettlementBatch.created_at)
    query = query.order_by(col.asc() if sort_dir == "asc" else col.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    merchants = _merchant_map(db)
    month_start = _now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fee_q = (
        db.query(func.coalesce(func.sum(ShopSettlementBatch.platform_fee_cents), 0))
        .filter(ShopSettlementBatch.created_at >= month_start)
    )
    pending_q = db.query(func.coalesce(func.sum(ShopSettlementBatch.net_amount_cents), 0)).filter(
        ShopSettlementBatch.status == "pending"
    )
    rev_q = (
        db.query(func.coalesce(func.sum(ShopSettlementBatch.refund_reversal_cents), 0))
        .filter(ShopSettlementBatch.created_at >= month_start)
    )
    return {
        "items": [_batch_out(db, b, merchants) for b in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "stats": {
            "month_platform_fee_cents": int(fee_q.scalar() or 0),
            "pending_payout_cents": int(pending_q.scalar() or 0),
            "month_refund_reversal_cents": int(rev_q.scalar() or 0),
            "settlement_period": "weekly",
        },
    }


def get_batch(db: Session, batch_id: UUID) -> dict:
    b = db.get(ShopSettlementBatch, batch_id)
    if not b:
        raise HTTPException(status_code=404, detail="批次不存在")
    out = _batch_out(db, b)
    items = []
    for it in b.items:
        order_no = None
        if it.order_id:
            o = db.get(ShopOrder, it.order_id)
            order_no = o.order_no if o else None
        src_no = None
        if it.source_batch_id:
            src = db.get(ShopSettlementBatch, it.source_batch_id)
            src_no = src.batch_no if src else None
        items.append(
            {
                "id": str(it.id),
                "item_type": it.item_type,
                "item_type_label": ITEM_TYPE_LABEL.get(it.item_type, it.item_type),
                "order_id": str(it.order_id) if it.order_id else None,
                "order_no": order_no,
                "refund_id": str(it.refund_id) if it.refund_id else None,
                "source_batch_id": str(it.source_batch_id) if it.source_batch_id else None,
                "source_batch_no": src_no,
                "amount_cents": int(it.amount_cents or 0),
                "fee_cents": int(it.fee_cents or 0),
                "net_cents": int(it.amount_cents or 0) - int(it.fee_cents or 0),
                "note": it.note,
            }
        )
    carry_sources = []
    for it in items:
        if it["item_type"] != "period_carry_in" or not it["source_batch_id"]:
            continue
        src = db.get(ShopSettlementBatch, UUID(it["source_batch_id"]))
        carry_sources.append(
            {
                "id": it["source_batch_id"],
                "batch_no": it["source_batch_no"] or (src.batch_no if src else None),
                "amount_cents": it["amount_cents"],
                "period_start": src.period_start.isoformat() if src and src.period_start else None,
                "period_end": src.period_end.isoformat() if src and src.period_end else None,
                "status": src.status if src else None,
                "status_label": STATUS_LABEL.get(src.status, src.status) if src else None,
                "net_amount_cents": int(src.net_amount_cents or 0) if src else it["amount_cents"],
            }
        )
    out["items"] = items
    out["carry_sources"] = carry_sources
    return out


def _require_batch(db: Session, batch_id: UUID) -> ShopSettlementBatch:
    b = db.get(ShopSettlementBatch, batch_id)
    if not b:
        raise HTTPException(status_code=404, detail="批次不存在")
    return b


def confirm_payout(
    db: Session,
    user: User,
    batch_id: UUID,
    *,
    remark: str | None = None,
    transfer_voucher_url: str | None = None,
) -> dict:
    b = _require_batch(db, batch_id)
    if b.status != "pending":
        raise HTTPException(status_code=422, detail="仅待结算可打款")
    if int(b.net_amount_cents or 0) <= 0:
        raise HTTPException(status_code=422, detail="仅待结算可打款")
    acct = _payout_account(db, b.tenant_id)
    if not acct["valid"]:
        raise HTTPException(status_code=422, detail="收款账户异常")
    now = _now()
    b.status = "paid"
    b.paid_at = now
    b.operator_id = user.id
    b.confirm_remark = remark
    b.fail_reason = None
    if transfer_voucher_url:
        b.transfer_voucher_url = transfer_voucher_url
    if int(b.opening_balance_cents or 0) < 0:
        carry_ids = [
            it.source_batch_id
            for it in b.items
            if it.item_type == "period_carry_in" and it.source_batch_id
        ]
        for cid in carry_ids:
            src = db.get(ShopSettlementBatch, cid)
            if src and src.status == "carried_forward":
                src.status = "offset_settled"
                src.offset_by_batch_id = b.id
                src.offset_settled_at = now
    db.commit()
    db.refresh(b)
    return get_batch(db, b.id)


def retry_payout(
    db: Session,
    user: User,
    batch_id: UUID,
    *,
    action: str,
) -> dict:
    b = _require_batch(db, batch_id)
    if b.status != "payment_failed":
        raise HTTPException(status_code=422, detail="仅打款失败可重试")
    if action == "return_pending":
        b.status = "pending"
        db.commit()
        db.refresh(b)
        return get_batch(db, b.id)
    if action != "retry":
        raise HTTPException(status_code=422, detail="处理方式须为重试或退回待结算")
    b.status = "pending"
    db.flush()
    return confirm_payout(db, user, b.id)


def export_list_csv(
    db: Session,
    *,
    columns: list[str] | None = None,
    raise_too_many: bool = False,
    **kwargs,
) -> str:
    kwargs.pop("columns", None)
    kwargs.pop("raise_too_many", None)
    data = list_batches(db, page=1, page_size=5000, **kwargs)
    if raise_too_many and int(data.get("total") or 0) > 5000:
        raise HTTPException(status_code=422, detail="结果过多，请缩小筛选")
    default_headers = [
        "结算批次",
        "商家",
        "周期",
        "成交额(分)",
        "平台抽成(分)",
        "退款冲正(分)",
        "应结(分)",
        "生成时间",
        "状态",
    ]
    col_map = {
        "batch_no": ["结算批次"],
        "merchant_name": ["商家"],
        "period": ["周期"],
        "gross": ["成交额(分)"],
        "fee": ["平台抽成(分)"],
        "reversal": ["退款冲正(分)"],
        "net": ["应结(分)"],
        "generated_at": ["生成时间"],
        "status": ["状态"],
        "paid_at": ["打款时间"],
        "operator_name": ["打款人"],
        "opening": ["上期结转(分)"],
    }
    if columns:
        headers: list[str] = []
        seen: set[str] = set()
        for key in columns:
            for h in col_map.get(key, []):
                if h not in seen:
                    seen.add(h)
                    headers.append(h)
        headers = headers or default_headers
    else:
        headers = default_headers
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for it in data["items"]:
        values = {
            "结算批次": it.get("batch_no") or "",
            "商家": it.get("merchant_name") or "",
            "周期": f"{it.get('period_start') or ''}~{it.get('period_end') or ''}",
            "成交额(分)": it.get("gross_amount_cents") or 0,
            "平台抽成(分)": it.get("platform_fee_cents") or 0,
            "退款冲正(分)": it.get("refund_reversal_cents") or 0,
            "应结(分)": it.get("net_amount_cents") or 0,
            "生成时间": (it.get("generated_at") or "")[:16].replace("T", " "),
            "状态": it.get("status_label") or "",
            "打款时间": (it.get("paid_at") or "")[:16].replace("T", " "),
            "打款人": it.get("operator_name") or "",
            "上期结转(分)": it.get("opening_balance_cents") or 0,
        }
        w.writerow([values[h] for h in headers])
    return buf.getvalue()


def create_settlement_export_task(db: Session, user: User, body=None):
    from app.schemas.shop_platform import SettlementExportRequest
    from app.services.shop import export_task_service

    body = body or SettlementExportRequest()
    filters = {
        "q": body.q,
        "status": body.status,
        "view": body.view,
        "period_start": body.period_start,
        "period_end": body.period_end,
        "sort_by": body.sort_by,
        "sort_dir": body.sort_dir,
        "columns": body.columns,
    }
    csv_text = export_list_csv(
        db,
        q=body.q,
        status=body.status,
        view=body.view,
        period_start=body.period_start,
        period_end=body.period_end,
        sort_by=body.sort_by,
        sort_dir=body.sort_dir or "desc",
        columns=body.columns,
        raise_too_many=True,
    )
    return export_task_service.persist_csv_for_user(
        db,
        user,
        resource="settlements",
        file_name="shop-settlement-batches.csv",
        csv_text=csv_text,
        filters=filters,
    )


def get_settlement_export_task(db: Session, user: User, task_id: UUID):
    from app.services.shop import export_task_service

    return export_task_service.get_task_for_user(db, user, task_id, "settlements")


def read_settlement_export_file(db: Session, user: User, task_id: UUID) -> str:
    from app.services.shop import export_task_service

    return export_task_service.read_file_for_user(db, user, task_id, "settlements")


def export_voucher_csv(db: Session, batch_id: UUID) -> str:
    detail = get_batch(db, batch_id)
    if detail["status"] != "paid":
        raise HTTPException(status_code=422, detail="仅已打款批次可导出")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["结算凭证", detail["batch_no"]])
    w.writerow(["商家", detail["merchant_name"]])
    w.writerow(["周期", f"{detail['period_start']}~{detail['period_end']}"])
    w.writerow(["应结(分)", detail["net_amount_cents"]])
    w.writerow(["打款时间", (detail.get("paid_at") or "")[:16].replace("T", " ")])
    w.writerow(["打款人", detail.get("operator_name") or ""])
    w.writerow([])
    w.writerow(["类型", "关联", "金额(分)", "抽成(分)", "应结(分)"])
    for it in detail.get("items") or []:
        w.writerow(
            [
                it.get("item_type_label") or "",
                it.get("order_no") or it.get("source_batch_no") or "",
                it.get("amount_cents") or 0,
                it.get("fee_cents") or 0,
                it.get("net_cents") or 0,
            ]
        )
    return buf.getvalue()


def export_items_csv(db: Session, batch_id: UUID) -> str:
    detail = get_batch(db, batch_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["批次", detail["batch_no"]])
    w.writerow(["类型", "关联", "金额(分)", "抽成(分)", "应结(分)", "说明"])
    for it in detail.get("items") or []:
        w.writerow(
            [
                it.get("item_type_label") or "",
                it.get("order_no") or it.get("source_batch_no") or "",
                it.get("amount_cents") or 0,
                it.get("fee_cents") or 0,
                it.get("net_cents") or 0,
                it.get("note") or "",
            ]
        )
    return buf.getvalue()


def seed_batch(
    db: Session,
    tenant_id: UUID,
    shop_id: UUID,
    *,
    net_cents: int = 40150,
    batch_status: str = "pending",
    fail_reason: str | None = None,
    opening_cents: int = 0,
    source_batch_id: UUID | None = None,
) -> ShopSettlementBatch:
    """验收种子：不经 F10，写入一条批次。"""
    week_start, week_end = iso_week_bounds(_now().date())
    period_net = net_cents - opening_cents
    fee = abs(period_net) * 25 // 1000 if period_net > 0 else 0
    gross = period_net + fee if period_net > 0 else 0
    reversal = abs(period_net) if period_net < 0 else 0
    batch = ShopSettlementBatch(
        id=uuid4(),
        tenant_id=tenant_id,
        shop_id=shop_id,
        batch_no=generate_platform_number(db, "settlement_batch"),
        period_start=week_start,
        period_end=week_end,
        gross_amount_cents=gross,
        platform_fee_cents=fee,
        refund_reversal_cents=reversal,
        opening_balance_cents=opening_cents,
        period_net_cents=period_net,
        net_amount_cents=net_cents,
        status=batch_status,
        fail_reason=fail_reason,
    )
    db.add(batch)
    db.flush()
    db.add(
        ShopSettlementItem(
            id=uuid4(),
            batch_id=batch.id,
            item_type="order_income" if period_net >= 0 else "refund_reversal",
            amount_cents=gross if period_net >= 0 else -reversal,
            fee_cents=fee,
            note="验收种子",
        )
    )
    if source_batch_id:
        db.add(
            ShopSettlementItem(
                id=uuid4(),
                batch_id=batch.id,
                item_type="period_carry_in",
                source_batch_id=source_batch_id,
                amount_cents=opening_cents,
                fee_cents=0,
                note="验收结转",
            )
        )
    db.commit()
    db.refresh(batch)
    return batch


def seed_pending_batch(db: Session, tenant_id: UUID, shop_id: UUID, *, net_cents: int = 40150) -> ShopSettlementBatch:
    week_start, week_end = iso_week_bounds(_now().date())
    existing = _existing_batch(db, tenant_id, shop_id, week_end)
    if existing and existing.status == "pending":
        return existing
    return seed_batch(db, tenant_id, shop_id, net_cents=net_cents, batch_status="pending")
