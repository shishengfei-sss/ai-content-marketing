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
from app.models.crm import Payment, PaymentPlan
from app.schemas.crm_deals import PaymentCreate, PaymentPlanCreate, PaymentUpdate
from app.services.crm.crm_scope_service import assert_can_view_payment, assert_can_view_order, _perm_set
from app.services.crm.number_service import generate_number
from app.services.crm.order_service import require_order


def _generate_payment_number(db: Session, tenant_id: UUID) -> str:
    return generate_number(db, tenant_id, "payment")


# ---------------- 回款计划 ----------------


def list_plans_for_order(db: Session, tenant_id: UUID, order_id: UUID) -> list[PaymentPlan]:
    return (
        db.query(PaymentPlan)
        .filter(PaymentPlan.tenant_id == tenant_id, uuid_eq(PaymentPlan.order_id, order_id))
        .order_by(PaymentPlan.installment_no)
        .all()
    )


def create_plan(db: Session, ctx: TenantContext, order_id: UUID, data: PaymentPlanCreate) -> PaymentPlan:
    order = require_order(db, ctx, order_id)
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


def require_payment(db: Session, ctx: TenantContext, payment_id: UUID) -> Payment:
    p = get_payment(db, ctx.tenant_id, payment_id)
    if not p:
        raise HTTPException(status_code=404, detail="回款不存在")
    assert_can_view_payment(ctx, db, p.owner_user_id)
    return p


def create_payment(db: Session, ctx: TenantContext, data: PaymentCreate) -> Payment:
    # 校验订单可见
    order = require_order(db, ctx, data.order_id)
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
    if payment.status not in ("pending", "confirmed"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"回款已 {payment.status}，不可确认")
    payment.status = "confirmed"
    db.commit()
    db.refresh(payment)
    return payment


def reverse_payment(db: Session, ctx: TenantContext, payment: Payment) -> Payment:
    if payment.status != "confirmed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="仅已确认回款可冲销")
    payment.status = "reversed"
    db.commit()
    db.refresh(payment)
    return payment


def soft_delete_payment(db: Session, payment: Payment) -> None:
    payment.deleted_at = datetime.now(timezone.utc)
    db.commit()
