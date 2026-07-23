"""回款服务（v0.7 CRM-3）。

回款计划 + 实际回款 + 确认到账 + 冲销。
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Order, Payment, PaymentPlan
from app.schemas.crm_deals import PaymentCreate, PaymentPlanCreate, PaymentUpdate, ReceivableItemOut, ReceivableSummaryOut
from app.services.crm.crm_scope_service import (
    assert_can_mutate_payment,
    assert_can_view_payment,
    assert_can_view_order,
    _perm_set,
)
from app.services.crm.number_service import generate_number
from app.services.crm.order_service import require_order

# BR-PAY-01：回款（计划/实际）仅允许挂在已生效订单
_PAYMENT_ALLOWED_ORDER_STATUSES = frozenset({"confirmed", "executing", "completed"})


def _assert_order_allows_payment(order: Order) -> None:
    if order.status not in _PAYMENT_ALLOWED_ORDER_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"订单状态为 {order.status}，不可登记回款（仅已确认/执行中/已完成）",
        )


def _generate_payment_number(db: Session, tenant_id: UUID) -> str:
    return generate_number(db, tenant_id, "payment")


def _aging_bucket(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "d30"
    if days_overdue <= 60:
        return "d60"
    return "d90plus"


def list_receivables(db: Session, ctx: TenantContext) -> ReceivableSummaryOut:
    """按回款计划计算应收：outstanding = max(0, plan - order已确认回款分摊简化为订单级已回后按计划顺序冲销)。

    简化算法：订单已回总额按 plan.installment_no 顺序冲销各期计划，未冲完且已到期的计入账龄。
    """
    now = datetime.now(timezone.utc)
    plans = (
        db.query(PaymentPlan)
        .join(Order, Order.id == PaymentPlan.order_id)
        .filter(
            PaymentPlan.tenant_id == ctx.tenant_id,
            Order.tenant_id == ctx.tenant_id,
            Order.deleted_at.is_(None),
            Order.status.notin_(("draft", "cancelled", "superseded")),
        )
        .order_by(PaymentPlan.order_id, PaymentPlan.installment_no)
        .all()
    )
    if not plans:
        return ReceivableSummaryOut(items=[], buckets={"current": 0, "d30": 0, "d60": 0, "d90plus": 0}, total_outstanding=0)

    order_ids = list({p.order_id for p in plans})
    orders = {
        o.id: o
        for o in db.query(Order).filter(Order.id.in_(order_ids), Order.tenant_id == ctx.tenant_id).all()
    }
    pays = (
        db.query(Payment)
        .filter(
            Payment.tenant_id == ctx.tenant_id,
            Payment.order_id.in_(order_ids),
            Payment.deleted_at.is_(None),
            Payment.status == "confirmed",
        )
        .all()
    )
    paid_by_order: dict[UUID, float] = {oid: 0.0 for oid in order_ids}
    for p in pays:
        paid_by_order[p.order_id] = paid_by_order.get(p.order_id, 0.0) + float(p.amount or 0)

    remaining_paid = dict(paid_by_order)
    items: list[ReceivableItemOut] = []
    buckets = {"current": 0.0, "d30": 0.0, "d60": 0.0, "d90plus": 0.0}

    for pl in plans:
        plan_amt = float(pl.plan_amount or 0)
        covered = min(plan_amt, remaining_paid.get(pl.order_id, 0.0))
        remaining_paid[pl.order_id] = max(0.0, remaining_paid.get(pl.order_id, 0.0) - covered)
        outstanding = round(plan_amt - covered, 2)
        if outstanding <= 0:
            continue
        plan_dt = pl.plan_date
        if plan_dt is not None and plan_dt.tzinfo is None:
            plan_dt = plan_dt.replace(tzinfo=timezone.utc)
        days_overdue = 0
        if plan_dt is not None and plan_dt < now:
            days_overdue = (now.date() - plan_dt.date()).days
        bucket = _aging_bucket(days_overdue)
        order = orders.get(pl.order_id)
        items.append(
            ReceivableItemOut(
                order_id=pl.order_id,
                order_number=order.order_number if order else None,
                order_title=order.title if order else None,
                plan_id=pl.id,
                installment_no=pl.installment_no,
                plan_date=pl.plan_date,
                plan_amount=plan_amt,
                paid_amount=covered,
                outstanding=outstanding,
                days_overdue=days_overdue,
                aging_bucket=bucket,
            )
        )
        buckets[bucket] = round(buckets[bucket] + outstanding, 2)

    total = round(sum(i.outstanding for i in items), 2)
    return ReceivableSummaryOut(items=items, buckets=buckets, total_outstanding=total)


# ---------------- 回款计划 ----------------


def list_plans_for_order(db: Session, tenant_id: UUID, order_id: UUID) -> list[PaymentPlan]:
    return (
        db.query(PaymentPlan)
        .filter(PaymentPlan.tenant_id == tenant_id, uuid_eq(PaymentPlan.order_id, order_id))
        .order_by(PaymentPlan.installment_no)
        .all()
    )


def order_payment_summary(
    db: Session, tenant_id: UUID, order_ids: list[UUID]
) -> dict[UUID, dict[str, float]]:
    """批量计算订单：计划合计 / 已回合计 / 逾期（已过期计划金额 − 已回，下限 0）。"""
    if not order_ids:
        return {}
    now = datetime.now(timezone.utc)
    plans = (
        db.query(PaymentPlan)
        .filter(PaymentPlan.tenant_id == tenant_id, PaymentPlan.order_id.in_(order_ids))
        .all()
    )
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
    summary: dict[UUID, dict[str, float]] = {
        oid: {"plan_total": 0.0, "paid_total": 0.0, "overdue_amount": 0.0} for oid in order_ids
    }
    overdue_plan: dict[UUID, float] = {oid: 0.0 for oid in order_ids}
    for pl in plans:
        oid = pl.order_id
        if oid not in summary:
            continue
        amt = float(pl.plan_amount or 0)
        summary[oid]["plan_total"] += amt
        plan_dt = pl.plan_date
        if plan_dt is not None:
            if plan_dt.tzinfo is None:
                plan_dt = plan_dt.replace(tzinfo=timezone.utc)
            if plan_dt < now:
                overdue_plan[oid] += amt
    for p in pays:
        oid = p.order_id
        if oid not in summary:
            continue
        summary[oid]["paid_total"] += float(p.amount or 0)
    for oid, s in summary.items():
        s["plan_total"] = round(s["plan_total"], 2)
        s["paid_total"] = round(s["paid_total"], 2)
        s["overdue_amount"] = round(max(0.0, overdue_plan[oid] - s["paid_total"]), 2)
    return summary


def create_plan(db: Session, ctx: TenantContext, order_id: UUID, data: PaymentPlanCreate) -> PaymentPlan:
    order = require_order(db, ctx, order_id)
    _assert_order_allows_payment(order)
    plan = PaymentPlan(
        tenant_id=ctx.tenant_id,
        order_id=order.id,
        installment_no=data.installment_no,
        plan_date=data.plan_date,
        plan_amount=data.plan_amount,
        remark=data.remark,
        created_by_user_id=ctx.user.id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def delete_plan(db: Session, ctx: TenantContext, plan_id: UUID) -> None:
    plan = (
        db.query(PaymentPlan)
        .filter(PaymentPlan.id == plan_id, PaymentPlan.tenant_id == ctx.tenant_id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="回款计划不存在")
    # 校验订单可见
    assert_can_view_order(ctx, db, plan.order_id)
    db.delete(plan)
    db.commit()


# ---------------- 实际回款 ----------------


def get_payment(db: Session, tenant_id: UUID, payment_id: UUID) -> Payment | None:
    return (
        db.query(Payment)
        .filter(uuid_eq(Payment.id, payment_id), Payment.tenant_id == tenant_id, Payment.deleted_at.is_(None))
        .first()
    )


def order_customer_map(db: Session, tenant_id: UUID, order_ids: list[UUID]) -> dict[UUID, UUID | None]:
    """批量取订单 → 客户 id。"""
    if not order_ids:
        return {}
    rows = (
        db.query(Order.id, Order.customer_id)
        .filter(Order.tenant_id == tenant_id, Order.id.in_(order_ids), Order.deleted_at.is_(None))
        .all()
    )
    return {oid: cid for oid, cid in rows}


def require_payment(db: Session, ctx: TenantContext, payment_id: UUID) -> Payment:
    p = get_payment(db, ctx.tenant_id, payment_id)
    if not p:
        raise HTTPException(status_code=404, detail="回款不存在")
    assert_can_view_payment(ctx, db, p.owner_user_id)
    return p


def create_payment(db: Session, ctx: TenantContext, data: PaymentCreate) -> Payment:
    # 校验订单可见 + BR-PAY-01 状态
    order = require_order(db, ctx, data.order_id)
    _assert_order_allows_payment(order)
    owner_user_id = ctx.user.id
    if data.owner_user_id is not None and data.owner_user_id != ctx.user.id:
        if "crm.payment.edit" not in _perm_set(ctx):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        owner_user_id = data.owner_user_id
    payment_number = data.payment_number or _generate_payment_number(db, ctx.tenant_id)
    payment = Payment(
        tenant_id=ctx.tenant_id,
        order_id=order.id,
        payment_number=payment_number,
        plan_id=data.plan_id,
        amount=data.amount,
        paid_at=data.paid_at or datetime.now(timezone.utc),
        method=data.method,
        status=data.status,
        remark=data.remark,
        owner_user_id=owner_user_id,
        created_by_user_id=ctx.user.id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def update_payment(db: Session, ctx: TenantContext, payment: Payment, data: PaymentUpdate) -> Payment:
    perms = _perm_set(ctx)
    mutate_keys = set(data.model_fields_set) - {"owner_user_id"}
    if mutate_keys:
        assert_can_mutate_payment(ctx, payment)

    if data.owner_user_id is not None and data.owner_user_id != payment.owner_user_id:
        if "crm.payment.edit" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        payment.owner_user_id = data.owner_user_id
    if data.amount is not None:
        payment.amount = data.amount
    if data.paid_at is not None:
        payment.paid_at = data.paid_at
    if data.method is not None:
        payment.method = data.method
    if data.status is not None:
        payment.status = data.status
    if data.remark is not None:
        payment.remark = data.remark
    db.commit()
    db.refresh(payment)
    return payment


def confirm_payment(db: Session, ctx: TenantContext, payment: Payment) -> Payment:
    assert_can_mutate_payment(ctx, payment)
    if payment.status not in ("pending", "confirmed"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"回款已 {payment.status}，不可确认")
    order = require_order(db, ctx, payment.order_id)
    _assert_order_allows_payment(order)
    payment.status = "confirmed"
    db.commit()
    db.refresh(payment)
    return payment


def reverse_payment(db: Session, ctx: TenantContext, payment: Payment) -> Payment:
    assert_can_mutate_payment(ctx, payment)
    if payment.status != "confirmed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="仅已确认回款可冲销")
    payment.status = "reversed"
    db.commit()
    db.refresh(payment)
    return payment


def soft_delete_payment(db: Session, ctx: TenantContext, payment: Payment) -> None:
    assert_can_mutate_payment(ctx, payment)
    if payment.status in ("confirmed", "reversed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="已到账或已冲销的回款不可删除",
        )
    payment.deleted_at = datetime.now(timezone.utc)
    db.commit()
