"""合同服务（v0.7 + 状态机/审批/复制/批量增强）。

CRUD + 明细行 + 发送/签署/生效/终止 + 审批 + 转订单 + 续约草稿。
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import ApprovalInstance, Contract, ContractLine, Order, OrderLine
from app.schemas.crm_deals import (
    ContractBatchAction,
    ContractBatchActionResult,
    ContractCreate,
    ContractLineCreate,
    ContractOut,
    ContractUpdate,
)
from app.services.crm.crm_scope_service import assert_can_mutate_contract, assert_can_view_contract, _perm_set
from app.services.crm.number_service import generate_number
from app.services.crm.schema_service import validate_extra_data


def get_contract(db: Session, tenant_id: UUID, contract_id: UUID) -> Contract | None:
    return (
        db.query(Contract)
        .filter(uuid_eq(Contract.id, contract_id), Contract.tenant_id == tenant_id, Contract.deleted_at.is_(None))
        .first()
    )


def require_contract(db: Session, ctx: TenantContext, contract_id: UUID) -> Contract:
    c = get_contract(db, ctx.tenant_id, contract_id)
    if not c:
        raise HTTPException(status_code=404, detail="合同不存在")
    assert_can_view_contract(ctx, db, c.owner_user_id)
    return c


def _generate_contract_number(db: Session, tenant_id: UUID) -> str:
    return generate_number(db, tenant_id, "contract")


def _generate_order_number(db: Session, tenant_id: UUID) -> str:
    return generate_number(db, tenant_id, "order")


def _load_lines(db: Session, contract_id: UUID) -> list[ContractLine]:
    return (
        db.query(ContractLine)
        .filter(ContractLine.contract_id == contract_id)
        .order_by(ContractLine.sort_order, ContractLine.id)
        .all()
    )


def _replace_lines(db: Session, contract: Contract, lines: list[ContractLineCreate]) -> None:
    from app.services.crm.tax_engine import TaxLineIn, compute_tax_lines

    db.query(ContractLine).filter(ContractLine.contract_id == contract.id).delete(synchronize_session=False)
    engine_in = [
        TaxLineIn(
            unit_price=ln.unit_price,
            quantity=ln.quantity,
            discount_rate=ln.discount_rate,
            tax_rate=ln.tax_rate,
        )
        for ln in lines
    ]
    result = compute_tax_lines(engine_in)
    for i, (ln, out) in enumerate(zip(lines, result.lines)):
        db.add(
            ContractLine(
                tenant_id=contract.tenant_id,
                contract_id=contract.id,
                product_id=ln.product_id,
                name=ln.name,
                unit=ln.unit,
                quantity=ln.quantity,
                unit_price=ln.unit_price,
                discount_rate=ln.discount_rate,
                tax_rate=float(out.tax_rate) if out.tax_rate is not None else ln.tax_rate,
                tax_amount=float(out.tax_amount),
                line_total=float(out.line_total),
                sort_order=ln.sort_order if ln.sort_order is not None else i,
                remark=ln.remark,
            )
        )
    db.flush()


def _recompute_amount(db: Session, contract: Contract) -> None:
    lines = _load_lines(db, contract.id)
    total = sum(float(l.line_total) for l in lines)
    contract.amount = round(total, 2)


def _related_order_stats(db: Session, contract_id: UUID) -> tuple[int, float]:
    rows = (
        db.query(Order)
        .filter(
            Order.contract_id == contract_id,
            Order.deleted_at.is_(None),
            Order.status.notin_(("cancelled", "superseded")),
        )
        .all()
    )
    return len(rows), round(sum(float(o.amount or 0) for o in rows), 2)


def _has_related_orders(db: Session, contract_id: UUID) -> bool:
    row = (
        db.query(Order.id)
        .filter(Order.contract_id == contract_id, Order.deleted_at.is_(None))
        .first()
    )
    return row is not None


def _get_pending_contract_approval(db: Session, tenant_id: UUID, contract_id: UUID) -> ApprovalInstance | None:
    return (
        db.query(ApprovalInstance)
        .filter(
            ApprovalInstance.tenant_id == tenant_id,
            ApprovalInstance.entity_type == "contract",
            uuid_eq(ApprovalInstance.entity_id, contract_id),
            ApprovalInstance.status == "pending",
        )
        .order_by(ApprovalInstance.created_at.desc())
        .first()
    )


def create_contract(db: Session, ctx: TenantContext, data: ContractCreate) -> Contract:
    extra = validate_extra_data(db, ctx.tenant_id, "contract", data.extra_data, is_create=True)
    owner_user_id = ctx.user.id
    if data.owner_user_id is not None and data.owner_user_id != ctx.user.id:
        if "crm.contract.edit" not in _perm_set(ctx):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        owner_user_id = data.owner_user_id
    contract_number = data.contract_number or _generate_contract_number(db, ctx.tenant_id)
    contract = Contract(
        tenant_id=ctx.tenant_id,
        contract_number=contract_number,
        deal_id=data.deal_id,
        customer_id=data.customer_id,
        quote_id=data.quote_id,
        title=data.title.strip(),
        contract_type=data.contract_type,
        amount=data.amount,
        signed_amount=data.signed_amount,
        start_date=data.start_date,
        end_date=data.end_date,
        status=data.status,
        owner_user_id=owner_user_id,
        file_url=data.file_url,
        extra_data=extra,
        created_by_user_id=ctx.user.id,
    )
    db.add(contract)
    db.flush()
    if data.lines:
        _replace_lines(db, contract, data.lines)
        _recompute_amount(db, contract)
    db.commit()
    db.refresh(contract)
    return contract


def update_contract(db: Session, ctx: TenantContext, contract: Contract, data: ContractUpdate) -> Contract:
    perms = _perm_set(ctx)
    mutate_keys = set(data.model_fields_set) - {"owner_user_id"}
    if mutate_keys:
        assert_can_mutate_contract(ctx, contract)

    locked = contract.status not in ("draft", "sent", "rejected")
    if locked:
        forbidden = {"amount", "signed_amount", "lines", "start_date", "end_date", "customer_id"}
        touched = mutate_keys & forbidden
        if touched:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"合同已 {contract.status}，不可直接修改 {', '.join(sorted(touched))}；请走补充协议",
            )

    if data.owner_user_id is not None and data.owner_user_id != contract.owner_user_id:
        if "crm.contract.edit" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        contract.owner_user_id = data.owner_user_id
    if data.deal_id is not None:
        contract.deal_id = data.deal_id
    if data.customer_id is not None:
        contract.customer_id = data.customer_id
    if data.quote_id is not None:
        contract.quote_id = data.quote_id
    if data.title is not None:
        contract.title = data.title.strip()
    if data.contract_type is not None:
        contract.contract_type = data.contract_type
    if data.amount is not None:
        contract.amount = data.amount
    if data.signed_amount is not None:
        contract.signed_amount = data.signed_amount
    if data.start_date is not None:
        contract.start_date = data.start_date
    if data.end_date is not None:
        contract.end_date = data.end_date
    if data.file_url is not None:
        contract.file_url = data.file_url
    if data.extra_data is not None:
        merged = dict(contract.extra_data or {})
        merged.update(data.extra_data)
        contract.extra_data = validate_extra_data(db, ctx.tenant_id, "contract", merged)
    if data.lines is not None:
        _replace_lines(db, contract, data.lines)
        _recompute_amount(db, contract)
    db.commit()
    db.refresh(contract)
    return contract


def send_contract(db: Session, ctx: TenantContext, contract: Contract) -> Contract:
    assert_can_mutate_contract(ctx, contract)
    if contract.status not in ("draft", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"合同状态为 {contract.status}，不可发送",
        )
    contract.status = "sent"
    db.commit()
    db.refresh(contract)
    return contract


def activate_contract(db: Session, ctx: TenantContext, contract: Contract) -> Contract:
    assert_can_mutate_contract(ctx, contract)
    if contract.status != "signed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"合同状态为 {contract.status}，不可开始执行",
        )
    contract.status = "executing"
    db.commit()
    db.refresh(contract)
    return contract


def terminate_contract(db: Session, ctx: TenantContext, contract: Contract) -> Contract:
    assert_can_mutate_contract(ctx, contract)
    if contract.status not in ("signed", "executing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"合同状态为 {contract.status}，不可终止",
        )
    contract.status = "terminated"
    db.commit()
    db.refresh(contract)
    return contract


def sign_contract(
    db: Session,
    ctx: TenantContext,
    contract: Contract,
    signed_amount: float | None = None,
    signed_at: datetime | None = None,
) -> Contract:
    assert_can_mutate_contract(ctx, contract)
    if contract.status == "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="合同审批中，请等待审批通过后再签署",
        )
    if contract.status not in ("draft", "sent"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"合同已 {contract.status}，不可签署")
    # 草稿直签：若命中金额审批规则，须先 submit；已发送（含审批通过）可直接签
    if contract.status == "draft":
        from app.services.crm.order_service import list_matching_approval_rules

        amount = float(signed_amount if signed_amount is not None else contract.amount or 0)
        rules = list_matching_approval_rules(db, ctx.tenant_id, amount)
        if rules:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="合同金额命中审批规则，请先调用 /submit 提交审批",
            )
    contract.status = "signed"
    contract.signed_at = signed_at or datetime.now(timezone.utc)
    if signed_amount is not None:
        contract.signed_amount = signed_amount
    elif contract.signed_amount is None:
        contract.signed_amount = contract.amount
    db.commit()
    db.refresh(contract)
    return contract


def submit_contract(db: Session, ctx: TenantContext, contract: Contract) -> Contract:
    """提交签署审批：无规则 → sent；有规则 → pending_approval。"""
    assert_can_mutate_contract(ctx, contract)
    if contract.status not in ("draft", "sent", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"合同状态为 {contract.status}，不可提交审批",
        )
    if _get_pending_contract_approval(db, ctx.tenant_id, contract.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已有进行中的审批")

    from app.services.crm.order_service import list_matching_approval_rules

    amount = float(contract.signed_amount if contract.signed_amount is not None else contract.amount or 0)
    rules = list_matching_approval_rules(db, ctx.tenant_id, amount)
    if not rules:
        if contract.status != "sent":
            contract.status = "sent"
        db.commit()
        db.refresh(contract)
        return contract

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
        entity_type="contract",
        entity_id=contract.id,
        rule_id=rules[0].id,
        status="pending",
        current_step=1,
        steps_json=steps,
        submitted_by_user_id=ctx.user.id,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(inst)
    contract.status = "pending_approval"
    db.commit()
    db.refresh(contract)
    return contract


def approve_contract(db: Session, ctx: TenantContext, contract: Contract) -> Contract:
    if contract.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"合同状态为 {contract.status}，不可审批",
        )
    inst = _get_pending_contract_approval(db, ctx.tenant_id, contract.id)
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
        db.refresh(contract)
        return contract

    inst.steps_json = steps
    inst.status = "approved"
    inst.resolved_at = now
    contract.status = "sent"
    db.commit()
    db.refresh(contract)
    return contract


def reject_contract(db: Session, ctx: TenantContext, contract: Contract, reason: str) -> Contract:
    if contract.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"合同状态为 {contract.status}，不可驳回",
        )
    inst = _get_pending_contract_approval(db, ctx.tenant_id, contract.id)
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
    inst.reject_reason = reason
    inst.resolved_at = now
    contract.status = "rejected"
    db.commit()
    db.refresh(contract)
    return contract


def withdraw_contract(db: Session, ctx: TenantContext, contract: Contract) -> Contract:
    assert_can_mutate_contract(ctx, contract)
    if contract.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"合同状态为 {contract.status}，不可撤回",
        )
    inst = _get_pending_contract_approval(db, ctx.tenant_id, contract.id)
    if inst:
        inst.status = "cancelled"
        inst.resolved_at = datetime.now(timezone.utc)
    contract.status = "draft"
    db.commit()
    db.refresh(contract)
    return contract


def soft_delete_contract(db: Session, ctx: TenantContext, contract: Contract) -> None:
    assert_can_mutate_contract(ctx, contract)
    if contract.status not in ("draft", "sent", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"合同状态为 {contract.status}，不可删除",
        )
    if _has_related_orders(db, contract.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="合同已关联订单，不可删除")
    contract.deleted_at = datetime.now(timezone.utc)
    db.commit()


def clone_contract(db: Session, ctx: TenantContext, contract: Contract) -> Contract:
    assert_can_view_contract(ctx, db, contract.owner_user_id)
    if "crm.contract.create" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限创建合同")
    src_lines = _load_lines(db, contract.id)
    line_payload = [
        ContractLineCreate(
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
    return create_contract(
        db,
        ctx,
        ContractCreate(
            title=f"{contract.title}（复制）"[:200],
            customer_id=contract.customer_id,
            deal_id=contract.deal_id,
            quote_id=contract.quote_id,
            contract_type=contract.contract_type,
            amount=float(contract.amount or 0),
            start_date=contract.start_date,
            end_date=contract.end_date,
            status="draft",
            owner_user_id=ctx.user.id,
            extra_data={"cloned_from": str(contract.id)},
            lines=line_payload,
        ),
    )


def renew_as_contract(db: Session, ctx: TenantContext, contract: Contract) -> Contract:
    """生成续约草稿合同。"""
    assert_can_view_contract(ctx, db, contract.owner_user_id)
    if contract.status not in ("signed", "executing", "expired"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"合同状态为 {contract.status}，不可续约",
        )
    if "crm.contract.create" not in _perm_set(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限创建合同")
    src_lines = _load_lines(db, contract.id)
    line_payload = [
        ContractLineCreate(
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
    amount = float(contract.signed_amount if contract.signed_amount is not None else contract.amount or 0)
    return create_contract(
        db,
        ctx,
        ContractCreate(
            title=f"{contract.title}（续约）"[:200],
            customer_id=contract.customer_id,
            deal_id=contract.deal_id,
            quote_id=contract.quote_id,
            contract_type="renewal",
            amount=amount,
            status="draft",
            owner_user_id=ctx.user.id,
            extra_data={"renewed_from": str(contract.id)},
            lines=line_payload,
        ),
    )


def batch_contract_action(
    db: Session, ctx: TenantContext, data: ContractBatchAction
) -> ContractBatchActionResult:
    succeeded = 0
    errors: list[dict] = []
    for cid in data.contract_ids:
        try:
            c = require_contract(db, ctx, cid)
            if data.action == "send":
                send_contract(db, ctx, c)
            elif data.action == "sign":
                if "crm.contract.sign" not in _perm_set(ctx):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限签署")
                sign_contract(db, ctx, c)
            succeeded += 1
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, str) else str(e.detail)
            errors.append({"contract_id": str(cid), "detail": detail})
        except Exception as e:  # noqa: BLE001
            errors.append({"contract_id": str(cid), "detail": str(e)})
    return ContractBatchActionResult(succeeded=succeeded, failed=len(errors), errors=errors)


def contract_to_out(db: Session, contract: Contract) -> ContractOut:
    amount = float(contract.amount or 0)
    signed = float(contract.signed_amount) if contract.signed_amount is not None else None
    amount_diff = round(signed - amount, 2) if signed is not None else None
    order_count, order_amount = _related_order_stats(db, contract.id)
    days_remaining = None
    if contract.end_date is not None:
        end = contract.end_date
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        today = datetime.now(timezone.utc).date()
        days_remaining = (end.astimezone(timezone.utc).date() - today).days
    base = ContractOut.model_validate(contract)
    return base.model_copy(
        update={
            "amount_diff": amount_diff,
            "related_order_count": order_count,
            "related_order_amount": order_amount,
            "days_remaining": days_remaining,
        }
    )


def convert_contract_to_order(db: Session, ctx: TenantContext, contract: Contract) -> Order:
    """合同转订单（source=contract）。合同可重复生成订单；有明细时一并复制。"""
    assert_can_mutate_contract(ctx, contract)
    if contract.status not in ("signed", "executing"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="合同未签署，不可转订单")
    amount = float(contract.signed_amount if contract.signed_amount is not None else contract.amount)
    order = Order(
        tenant_id=ctx.tenant_id,
        order_number=_generate_order_number(db, ctx.tenant_id),
        title=f"由合同「{contract.title}」生成",
        customer_id=contract.customer_id,
        contact_id=None,
        deal_id=contract.deal_id,
        quote_id=contract.quote_id,
        contract_id=contract.id,
        source="contract",
        order_date=datetime.now(timezone.utc),
        amount=amount,
        status="draft",
        owner_user_id=contract.owner_user_id,
        territory_id=None,
        extra_data={},
        created_by_user_id=ctx.user.id,
    )
    db.add(order)
    db.flush()
    contract_lines = _load_lines(db, contract.id)
    for i, ln in enumerate(contract_lines):
        db.add(
            OrderLine(
                tenant_id=ctx.tenant_id,
                order_id=order.id,
                product_id=ln.product_id,
                name=ln.name,
                unit=ln.unit,
                quantity=ln.quantity,
                unit_price=ln.unit_price,
                discount_rate=ln.discount_rate,
                tax_rate=ln.tax_rate,
                tax_amount=ln.tax_amount,
                line_total=ln.line_total,
                sort_order=ln.sort_order if ln.sort_order is not None else i,
                remark=ln.remark,
            )
        )
    if contract_lines:
        order.amount = round(sum(float(l.line_total) for l in contract_lines), 2)
    db.commit()
    db.refresh(order)
    return order
