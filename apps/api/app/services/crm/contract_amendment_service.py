"""合同补充协议（v1.0 P1-E）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import CONTRACT_AMENDMENT_CHANGE_TYPES, CONTRACT_AMENDMENT_STATUSES, ContractAmendment
from app.schemas.crm_deals import ContractAmendmentCreate, ContractAmendmentUpdate
from app.services.crm.contract_service import require_contract
from app.services.crm.number_service import generate_number


def list_amendments(db: Session, ctx: TenantContext, contract_id: UUID) -> list[ContractAmendment]:
    require_contract(db, ctx, contract_id)
    return (
        db.query(ContractAmendment)
        .filter(
            ContractAmendment.tenant_id == ctx.tenant_id,
            ContractAmendment.parent_contract_id == contract_id,
        )
        .order_by(ContractAmendment.created_at.desc())
        .all()
    )


def create_amendment(
    db: Session, ctx: TenantContext, contract_id: UUID, data: ContractAmendmentCreate
) -> ContractAmendment:
    require_contract(db, ctx, contract_id)
    if data.change_type not in CONTRACT_AMENDMENT_CHANGE_TYPES:
        raise HTTPException(status_code=422, detail=f"change_type 无效: {data.change_type}")
    row = ContractAmendment(
        tenant_id=ctx.tenant_id,
        parent_contract_id=contract_id,
        amendment_number=generate_number(db, ctx.tenant_id, "contract_amendment"),
        title=data.title.strip(),
        change_type=data.change_type,
        original_value=data.original_value,
        new_value=data.new_value,
        amount_delta=data.amount_delta,
        status="draft",
        created_by_user_id=ctx.user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_amendment(db: Session, tenant_id: UUID, amendment_id: UUID) -> ContractAmendment | None:
    return (
        db.query(ContractAmendment)
        .filter(ContractAmendment.id == amendment_id, ContractAmendment.tenant_id == tenant_id)
        .first()
    )


def update_amendment(
    db: Session, ctx: TenantContext, amendment: ContractAmendment, data: ContractAmendmentUpdate
) -> ContractAmendment:
    require_contract(db, ctx, amendment.parent_contract_id)
    if amendment.status not in ("draft",):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="仅草稿可编辑")
    if data.title is not None:
        amendment.title = data.title.strip()
    if data.change_type is not None:
        if data.change_type not in CONTRACT_AMENDMENT_CHANGE_TYPES:
            raise HTTPException(status_code=422, detail="change_type 无效")
        amendment.change_type = data.change_type
    if data.original_value is not None:
        amendment.original_value = data.original_value
    if data.new_value is not None:
        amendment.new_value = data.new_value
    if data.amount_delta is not None:
        amendment.amount_delta = data.amount_delta
    if data.status is not None:
        if data.status not in CONTRACT_AMENDMENT_STATUSES:
            raise HTTPException(status_code=422, detail="status 无效")
        amendment.status = data.status
    db.commit()
    db.refresh(amendment)
    return amendment


def approve_amendment(db: Session, ctx: TenantContext, amendment: ContractAmendment) -> ContractAmendment:
    require_contract(db, ctx, amendment.parent_contract_id)
    if amendment.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="仅草稿可批准")
    amendment.status = "approved"
    db.commit()
    db.refresh(amendment)
    return amendment


def execute_amendment(db: Session, ctx: TenantContext, amendment: ContractAmendment) -> ContractAmendment:
    contract = require_contract(db, ctx, amendment.parent_contract_id)
    if amendment.status not in ("draft", "approved"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前状态不可执行")
    if amendment.change_type == "amount_change" and amendment.amount_delta is not None:
        contract.amount = float(contract.amount or 0) + float(amendment.amount_delta)
    amendment.status = "executed"
    db.commit()
    db.refresh(amendment)
    return amendment
