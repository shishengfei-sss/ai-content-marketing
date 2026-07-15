"""订单服务（v0.7 + v1.0 P0 审批/税率）。

CRUD + 订单行 + 下单确认/提交审批/审批通过驳回 + 取消。
无匹配审批规则时 confirm/submit 可直接 confirmed；有规则则走 pending_approval。
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import ApprovalInstance, Order, OrderApprovalRule, OrderLine
from app.schemas.crm_deals import (
    OrderApprovalRuleCreate,
    OrderApprovalRuleUpdate,
    OrderCreate,
    OrderLineCreate,
    OrderUpdate,
)
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


def _line_amounts(ln: OrderLineCreate) -> tuple[float, float | None]:
    """返回 (line_total 折后未税, tax_amount)。"""
    line_total = ln.line_total if ln.line_total else float(ln.quantity) * float(ln.unit_price) * (
        1 - (float(ln.discount_rate or 0) / 100)
    )
    line_total = round(float(line_total), 2)
    tax_amount = ln.tax_amount
    if tax_amount is None and ln.tax_rate is not None:
        tax_amount = round(line_total * float(ln.tax_rate) / 100, 2)
    return line_total, tax_amount


def _replace_lines(db: Session, order: Order, lines: list[OrderLineCreate]) -> None:
    db.query(OrderLine).filter(OrderLine.order_id == order.id).delete(synchronize_session=False)
    for i, ln in enumerate(lines):
        line_total, tax_amount = _line_amounts(ln)
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
                tax_rate=ln.tax_rate,
                tax_amount=tax_amount,
                line_total=line_total,
                sort_order=ln.sort_order if ln.sort_order is not None else i,
                remark=ln.remark,
            )
        )
    db.flush()


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
        parent_order_id=None,
        version=1,
        revision_reason=None,
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


def list_matching_approval_rules(
    db: Session, tenant_id: UUID, amount: float
) -> list[OrderApprovalRule]:
    amount_f = float(amount)
    rules = (
        db.query(OrderApprovalRule)
        .filter(
            OrderApprovalRule.tenant_id == tenant_id,
            OrderApprovalRule.is_active.is_(True),
            OrderApprovalRule.min_amount <= amount_f,
        )
        .order_by(OrderApprovalRule.min_amount.desc())
        .all()
    )
    matched: list[OrderApprovalRule] = []
    for r in rules:
        if r.max_amount is None or float(r.max_amount) >= amount_f:
            matched.append(r)
    return matched


def get_pending_approval(db: Session, tenant_id: UUID, order_id: UUID) -> ApprovalInstance | None:
    return (
        db.query(ApprovalInstance)
        .filter(
            ApprovalInstance.tenant_id == tenant_id,
            ApprovalInstance.entity_type == "order",
            uuid_eq(ApprovalInstance.entity_id, order_id),
            ApprovalInstance.status == "pending",
        )
        .order_by(ApprovalInstance.created_at.desc())
        .first()
    )


def list_order_approvals(
    db: Session, tenant_id: UUID, order_id: UUID
) -> list[ApprovalInstance]:
    return (
        db.query(ApprovalInstance)
        .filter(
            ApprovalInstance.tenant_id == tenant_id,
            ApprovalInstance.entity_type == "order",
            uuid_eq(ApprovalInstance.entity_id, order_id),
        )
        .order_by(ApprovalInstance.created_at.desc())
        .all()
    )


def _create_approval_instance(
    db: Session, ctx: TenantContext, order: Order, rules: list[OrderApprovalRule]
) -> ApprovalInstance:
    primary = rules[0]
    steps = [
        {
            "step": idx + 1,
            "rule_id": str(r.id),
            "approver_role": r.approver_role,
            "status": "pending" if idx == 0 else "waiting",
        }
        for idx, r in enumerate(rules)
    ]
    inst = ApprovalInstance(
        tenant_id=ctx.tenant_id,
        entity_type="order",
        entity_id=order.id,
        rule_id=primary.id,
        status="pending",
        current_step=1,
        steps_json=steps,
        submitted_by_user_id=ctx.user.id,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(inst)
    db.flush()
    return inst


def confirm_order(db: Session, ctx: TenantContext, order: Order) -> Order:
    """无匹配审批规则时直接 confirmed；有规则则 409 提示走 submit。"""
    if order.status == "superseded":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已修订订单不可确认")
    if order.status not in ("draft", "rejected", "approved"):
        if order.status == "confirmed":
            return order
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"订单已 {order.status}，不可确认",
        )
    rules = list_matching_approval_rules(db, ctx.tenant_id, order.amount)
    if rules:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="订单金额命中审批规则，请调用 /submit 提交审批",
        )
    order.status = "confirmed"
    db.commit()
    db.refresh(order)
    return order


def submit_order(db: Session, ctx: TenantContext, order: Order) -> Order:
    """提交审批：无规则则直接 confirmed；有规则 → pending_approval。"""
    if order.status == "superseded":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已修订订单不可提交")
    if order.status not in ("draft", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"订单状态为 {order.status}，不可提交审批",
        )
    pending = get_pending_approval(db, ctx.tenant_id, order.id)
    if pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已有进行中的审批")

    rules = list_matching_approval_rules(db, ctx.tenant_id, order.amount)
    if not rules:
        order.status = "confirmed"
        db.commit()
        db.refresh(order)
        return order

    _create_approval_instance(db, ctx, order, rules)
    order.status = "pending_approval"
    db.commit()
    db.refresh(order)
    return order


def approve_order(db: Session, ctx: TenantContext, order: Order) -> Order:
    if order.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"订单状态为 {order.status}，不可审批",
        )
    inst = get_pending_approval(db, ctx.tenant_id, order.id)
    if not inst:
        raise HTTPException(status_code=404, detail="无待审批实例")

    now = datetime.now(timezone.utc)
    steps = list(inst.steps_json or [])
    step_idx = max(inst.current_step - 1, 0)
    if step_idx < len(steps):
        steps[step_idx] = {
            **steps[step_idx],
            "status": "approved",
            "acted_by": str(ctx.user.id),
            "acted_at": now.isoformat(),
        }

    all_approved = bool(steps) and all(s.get("status") == "approved" for s in steps)
    if not all_approved and step_idx + 1 < len(steps):
        steps[step_idx + 1] = {**steps[step_idx + 1], "status": "pending"}
        inst.current_step = step_idx + 2
        inst.steps_json = steps
        db.commit()
        db.refresh(order)
        return order

    inst.steps_json = steps
    inst.status = "approved"
    inst.resolved_at = now
    order.status = "confirmed"
    db.commit()
    db.refresh(order)
    return order


def reject_order(db: Session, ctx: TenantContext, order: Order, reason: str) -> Order:
    if order.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"订单状态为 {order.status}，不可驳回",
        )
    inst = get_pending_approval(db, ctx.tenant_id, order.id)
    if not inst:
        raise HTTPException(status_code=404, detail="无待审批实例")

    now = datetime.now(timezone.utc)
    steps = list(inst.steps_json or [])
    step_idx = max(inst.current_step - 1, 0)
    if step_idx < len(steps):
        steps[step_idx] = {
            **steps[step_idx],
            "status": "rejected",
            "acted_by": str(ctx.user.id),
            "acted_at": now.isoformat(),
            "reason": reason,
        }
    inst.steps_json = steps
    inst.status = "rejected"
    inst.reject_reason = reason.strip()
    inst.resolved_at = now
    order.status = "rejected"
    db.commit()
    db.refresh(order)
    return order


def cancel_order(db: Session, ctx: TenantContext, order: Order) -> Order:
    if order.status in ("completed", "cancelled", "superseded"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"订单已 {order.status}，不可取消")
    if order.status == "pending_approval":
        inst = get_pending_approval(db, ctx.tenant_id, order.id)
        if inst:
            inst.status = "cancelled"
            inst.resolved_at = datetime.now(timezone.utc)
    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    return order


def revise_order(
    db: Session,
    ctx: TenantContext,
    order: Order,
    *,
    reason: str,
    lines: list[OrderLineCreate] | None = None,
    title: str | None = None,
) -> Order:
    """生成修订版订单：原单 superseded；新单复制后自动 submit 重审。"""
    if order.status not in ("confirmed", "executing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"订单状态为 {order.status}，不可修订",
        )
    src_lines = _load_lines(db, order.id)
    if not src_lines and not lines:
        raise HTTPException(status_code=400, detail="订单无明细，无法修订")

    line_payload: list[OrderLineCreate] = lines or [
        OrderLineCreate(
            product_id=ln.product_id,
            name=ln.name,
            unit=ln.unit,
            quantity=float(ln.quantity),
            unit_price=float(ln.unit_price),
            discount_rate=float(ln.discount_rate) if ln.discount_rate is not None else None,
            tax_rate=float(ln.tax_rate) if ln.tax_rate is not None else None,
            tax_amount=float(ln.tax_amount) if ln.tax_amount is not None else None,
            line_total=float(ln.line_total),
            sort_order=ln.sort_order,
            remark=ln.remark,
        )
        for ln in src_lines
    ]

    revised = Order(
        tenant_id=order.tenant_id,
        order_number=_generate_order_number(db, ctx.tenant_id),
        title=(title or order.title).strip(),
        customer_id=order.customer_id,
        contact_id=order.contact_id,
        deal_id=order.deal_id,
        quote_id=order.quote_id,
        contract_id=order.contract_id,
        source=order.source,
        order_date=datetime.now(timezone.utc),
        amount=0,
        status="draft",
        parent_order_id=order.id,
        version=int(order.version or 1) + 1,
        revision_reason=reason.strip(),
        owner_user_id=order.owner_user_id,
        territory_id=order.territory_id,
        extra_data=dict(order.extra_data or {}),
        created_by_user_id=ctx.user.id,
    )
    db.add(revised)
    db.flush()
    _replace_lines(db, revised, line_payload)
    _recompute_amount(db, revised)
    order.status = "superseded"
    db.flush()
    # 自动重审（submit 内部会 commit）
    return submit_order(db, ctx, revised)


def list_order_revisions(db: Session, ctx: TenantContext, order_id: UUID) -> list[Order]:
    """列出修订链（根单 + 全部修订版）。"""
    order = require_order(db, ctx, order_id)
    root = order
    guard = 0
    while root.parent_order_id and guard < 50:
        parent = get_order(db, ctx.tenant_id, root.parent_order_id)
        if not parent:
            break
        root = parent
        guard += 1

    result: list[Order] = [root]
    queue = [root.id]
    seen = {root.id}
    while queue:
        pid = queue.pop(0)
        children = (
            db.query(Order)
            .filter(
                Order.tenant_id == ctx.tenant_id,
                Order.parent_order_id == pid,
                Order.deleted_at.is_(None),
            )
            .order_by(Order.version.asc())
            .all()
        )
        for child in children:
            if child.id in seen:
                continue
            seen.add(child.id)
            result.append(child)
            queue.append(child.id)
    result.sort(key=lambda o: (int(o.version or 1), o.created_at or datetime.min.replace(tzinfo=timezone.utc)))
    return result


def soft_delete_order(db: Session, order: Order) -> None:
    order.deleted_at = datetime.now(timezone.utc)
    db.query(OrderLine).filter(OrderLine.order_id == order.id).delete(synchronize_session=False)
    db.commit()


# ---- 审批规则 CRUD ----


def list_approval_rules(db: Session, tenant_id: UUID) -> list[OrderApprovalRule]:
    return (
        db.query(OrderApprovalRule)
        .filter(OrderApprovalRule.tenant_id == tenant_id)
        .order_by(OrderApprovalRule.min_amount.asc())
        .all()
    )


def get_approval_rule(
    db: Session, tenant_id: UUID, rule_id: UUID
) -> OrderApprovalRule | None:
    return (
        db.query(OrderApprovalRule)
        .filter(uuid_eq(OrderApprovalRule.id, rule_id), OrderApprovalRule.tenant_id == tenant_id)
        .first()
    )


def create_approval_rule(
    db: Session, ctx: TenantContext, data: OrderApprovalRuleCreate
) -> OrderApprovalRule:
    if data.max_amount is not None and data.max_amount < data.min_amount:
        raise HTTPException(status_code=400, detail="max_amount 不能小于 min_amount")
    rule = OrderApprovalRule(
        tenant_id=ctx.tenant_id,
        name=data.name.strip(),
        min_amount=data.min_amount,
        max_amount=data.max_amount,
        approver_role=data.approver_role,
        approval_type=data.approval_type,
        is_active=data.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_approval_rule(
    db: Session, rule: OrderApprovalRule, data: OrderApprovalRuleUpdate
) -> OrderApprovalRule:
    if data.name is not None:
        rule.name = data.name.strip()
    if data.min_amount is not None:
        rule.min_amount = data.min_amount
    if data.max_amount is not None:
        rule.max_amount = data.max_amount
    if data.approver_role is not None:
        rule.approver_role = data.approver_role
    if data.approval_type is not None:
        rule.approval_type = data.approval_type
    if data.is_active is not None:
        rule.is_active = data.is_active
    min_a = float(rule.min_amount)
    max_a = float(rule.max_amount) if rule.max_amount is not None else None
    if max_a is not None and max_a < min_a:
        raise HTTPException(status_code=400, detail="max_amount 不能小于 min_amount")
    db.commit()
    db.refresh(rule)
    return rule


def delete_approval_rule(db: Session, rule: OrderApprovalRule) -> None:
    db.delete(rule)
    db.commit()
