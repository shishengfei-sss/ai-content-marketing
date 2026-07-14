"""合同服务（v0.7 CRM-2）。

CRUD + 签署 + 转订单（可重复生成订单）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Contract, Order
from app.schemas.crm_deals import ContractCreate, ContractUpdate
from app.services.crm.crm_scope_service import assert_can_view_contract, _perm_set
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
    db.commit()
    db.refresh(contract)
    return contract


def update_contract(db: Session, ctx: TenantContext, contract: Contract, data: ContractUpdate) -> Contract:
    perms = _perm_set(ctx)
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
    if data.status is not None:
        contract.status = data.status
    if data.file_url is not None:
        contract.file_url = data.file_url
    if data.extra_data is not None:
        merged = dict(contract.extra_data or {})
        merged.update(data.extra_data)
        contract.extra_data = validate_extra_data(db, ctx.tenant_id, "contract", merged)
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
    if contract.status not in ("draft", "sent", "signed"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"合同已 {contract.status}，不可签署")
    contract.status = "signed"
    contract.signed_at = signed_at or datetime.now(timezone.utc)
    if signed_amount is not None:
        contract.signed_amount = signed_amount
    db.commit()
    db.refresh(contract)
    return contract


def soft_delete_contract(db: Session, contract: Contract) -> None:
    contract.deleted_at = datetime.now(timezone.utc)
    db.commit()


def convert_contract_to_order(db: Session, ctx: TenantContext, contract: Contract) -> Order:
    """合同转订单（source=contract）。合同可重复生成订单。"""
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
    db.commit()
    db.refresh(order)
    return order
