"""订单服务（v0.7 CRM-2/3）。

CRUD + 订单行 + 下单确认（draft -> confirmed）+ 取消。
订单无审批流；可由商机/报价/合同转单（在各自服务中实现）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Order, OrderLine
from app.schemas.crm_deals import OrderCreate, OrderLineCreate, OrderUpdate
from app.services.crm.crm_scope_service import assert_can_view_order, _perm_set
from app.services.crm.number_service import generate_number
from app.services.crm.schema_service import validate_extra_data
from app.services.crm.sales_org_service import get_territory


def get_order(db: Session, tenant_id: UUID, order_id: UUID) -> Order | None:
    return (
        db.query(Order)
        .filter(uuid_eq(Order.id, order_id), Order.tenant_id == tenant_id, Order.deleted_at.is_(None))
        .first()
    )


def require_order(db: Session, ctx: TenantContext, order_id: UUID) -> Order:
    o = get_order(db, ctx.tenant_id, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    assert_can_view_order(ctx, db, o.owner_user_id)
    return o


def _load_lines(db: Session, order_id: UUID) -> list[OrderLine]:
    return (
        db.query(OrderLine)
        .filter(OrderLine.order_id == order_id)
        .order_by(OrderLine.sort_order, OrderLine.id)
        .all()
    )


def _generate_order_number(db: Session, tenant_id: UUID) -> str:
    return generate_number(db, tenant_id, "order")


def _replace_lines(db: Session, order: Order, lines: list[OrderLineCreate]) -> None:
    db.query(OrderLine).filter(OrderLine.order_id == order.id).delete(synchronize_session=False)
    for i, ln in enumerate(lines):
        line_total = ln.line_total if ln.line_total else float(ln.quantity) * float(ln.unit_price) * (
            1 - (float(ln.discount_rate or 0) / 100)
        )
        db.add(
            OrderLine(
                tenant_id=order.tenant_id,
                order_id=order.id,
                product_id=ln.product_id,
                name=ln.name,
                unit=ln.unit,
                quantity=ln.quantity,
                unit_price=ln.unit_price,
                discount_rate=ln.discount_rate,
                line_total=line_total,
                sort_order=ln.sort_order if ln.sort_order is not None else i,
                remark=ln.remark,
            )
        )
    db.flush()  # 确保新明细落库，供后续 _recompute_amount 查询


def _recompute_amount(db: Session, order: Order) -> None:
    lines = _load_lines(db, order.id)
    total = sum(float(l.line_total) for l in lines)
    order.amount = round(total, 2)


def create_order(db: Session, ctx: TenantContext, data: OrderCreate) -> Order:
    extra = validate_extra_data(db, ctx.tenant_id, "order", data.extra_data, is_create=True)
    owner_user_id = ctx.user.id
    if data.owner_user_id is not None and data.owner_user_id != ctx.user.id:
        if "crm.order.assign" not in _perm_set(ctx):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        owner_user_id = data.owner_user_id
    territory_id = data.territory_id
    if territory_id is not None and not get_territory(db, ctx.tenant_id, territory_id):
        raise HTTPException(status_code=404, detail="地区不存在")
    order_number = data.order_number or _generate_order_number(db, ctx.tenant_id)
    order = Order(
        tenant_id=ctx.tenant_id,
        order_number=order_number,
        title=data.title.strip(),
        customer_id=data.customer_id,
        contact_id=data.contact_id,
        deal_id=data.deal_id,
        quote_id=data.quote_id,
        contract_id=data.contract_id,
        source=data.source,
        order_date=data.order_date or datetime.now(timezone.utc),
        amount=data.amount,
        status=data.status,
        owner_user_id=owner_user_id,
        territory_id=territory_id,
        extra_data=extra,
        created_by_user_id=ctx.user.id,
    )
    db.add(order)
    db.flush()
    if data.lines:
        _replace_lines(db, order, data.lines)
        _recompute_amount(db, order)
    db.commit()
    db.refresh(order)
    return order


def update_order(db: Session, ctx: TenantContext, order: Order, data: OrderUpdate) -> Order:
    perms = _perm_set(ctx)
    if data.owner_user_id is not None and data.owner_user_id != order.owner_user_id:
        if "crm.order.assign" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        order.owner_user_id = data.owner_user_id
    if data.title is not None:
        order.title = data.title.strip()
    if data.customer_id is not None:
        order.customer_id = data.customer_id
    if data.contact_id is not None:
        order.contact_id = data.contact_id
    if data.deal_id is not None:
        order.deal_id = data.deal_id
    if data.quote_id is not None:
        order.quote_id = data.quote_id
    if data.contract_id is not None:
        order.contract_id = data.contract_id
    if data.source is not None:
        order.source = data.source
    if data.order_date is not None:
        order.order_date = data.order_date
    if data.amount is not None:
        order.amount = data.amount
    if data.status is not None:
        order.status = data.status
    if data.territory_id is not None:
        if not get_territory(db, ctx.tenant_id, data.territory_id):
            raise HTTPException(status_code=404, detail="地区不存在")
        order.territory_id = data.territory_id
    if data.extra_data is not None:
        merged = dict(order.extra_data or {})
        merged.update(data.extra_data)
        order.extra_data = validate_extra_data(db, ctx.tenant_id, "order", merged)
    if data.lines is not None:
        _replace_lines(db, order, data.lines)
    _recompute_amount(db, order)
    db.commit()
    db.refresh(order)
    return order


def confirm_order(db: Session, ctx: TenantContext, order: Order) -> Order:
    if order.status not in ("draft", "confirmed"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"订单已 {order.status}，不可确认")
    order.status = "confirmed"
    db.commit()
    db.refresh(order)
    return order


def cancel_order(db: Session, ctx: TenantContext, order: Order) -> Order:
    if order.status in ("completed", "cancelled"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"订单已 {order.status}，不可取消")
    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    return order


def soft_delete_order(db: Session, order: Order) -> None:
    order.deleted_at = datetime.now(timezone.utc)
    db.query(OrderLine).filter(OrderLine.order_id == order.id).delete(synchronize_session=False)
    db.commit()
