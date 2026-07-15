"""合同模板服务（v1.0 P0）。"""
from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Contract, ContractTemplate
from app.schemas.crm_deals import (
    ContractFromTemplateRequest,
    ContractTemplateCreate,
    ContractTemplateUpdate,
)
from app.services.crm.contract_service import _generate_contract_number
from app.services.crm.schema_service import validate_extra_data


def list_templates(db: Session, tenant_id: UUID, *, active_only: bool = False) -> list[ContractTemplate]:
    q = db.query(ContractTemplate).filter(ContractTemplate.tenant_id == tenant_id)
    if active_only:
        q = q.filter(ContractTemplate.is_active.is_(True))
    return q.order_by(ContractTemplate.updated_at.desc()).all()


def get_template(db: Session, tenant_id: UUID, template_id: UUID) -> ContractTemplate | None:
    return (
        db.query(ContractTemplate)
        .filter(uuid_eq(ContractTemplate.id, template_id), ContractTemplate.tenant_id == tenant_id)
        .first()
    )


def create_template(
    db: Session, ctx: TenantContext, data: ContractTemplateCreate
) -> ContractTemplate:
    tpl = ContractTemplate(
        tenant_id=ctx.tenant_id,
        name=data.name.strip(),
        category=data.category,
        content=data.content,
        variables=list(data.variables or []),
        is_active=data.is_active,
        created_by_user_id=ctx.user.id,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


def update_template(
    db: Session, tpl: ContractTemplate, data: ContractTemplateUpdate
) -> ContractTemplate:
    if data.name is not None:
        tpl.name = data.name.strip()
    if data.category is not None:
        tpl.category = data.category
    if data.content is not None:
        tpl.content = data.content
    if data.variables is not None:
        tpl.variables = list(data.variables)
    if data.is_active is not None:
        tpl.is_active = data.is_active
    db.commit()
    db.refresh(tpl)
    return tpl


def delete_template(db: Session, tpl: ContractTemplate) -> None:
    db.delete(tpl)
    db.commit()


def _render_content(content: str, values: dict) -> str:
    def repl(match: re.Match) -> str:
        key = match.group(1).strip()
        if key not in values:
            return match.group(0)
        return str(values[key])

    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", repl, content)


def create_contract_from_template(
    db: Session, ctx: TenantContext, data: ContractFromTemplateRequest
) -> Contract:
    tpl = get_template(db, ctx.tenant_id, data.template_id)
    if not tpl or not tpl.is_active:
        raise HTTPException(status_code=404, detail="合同模板不存在或已停用")
    rendered = _render_content(tpl.content, data.variable_values or {})
    title = (data.title or "").strip() or tpl.name
    amount = data.amount if data.amount is not None else 0
    if amount == 0 and "amount" in (data.variable_values or {}):
        try:
            amount = float(data.variable_values["amount"])
        except (TypeError, ValueError):
            amount = 0
    extra = validate_extra_data(
        db,
        ctx.tenant_id,
        "contract",
        {
            "template_id": str(tpl.id),
            "template_name": tpl.name,
            "body": rendered,
            **(data.extra_data or {}),
        },
        is_create=True,
    )
    contract = Contract(
        tenant_id=ctx.tenant_id,
        contract_number=_generate_contract_number(db, ctx.tenant_id),
        deal_id=data.deal_id,
        customer_id=data.customer_id,
        quote_id=None,
        title=title,
        contract_type=data.contract_type or "new",
        amount=amount,
        signed_amount=None,
        start_date=data.start_date,
        end_date=data.end_date,
        status="draft",
        owner_user_id=ctx.user.id,
        file_url=None,
        extra_data=extra,
        created_by_user_id=ctx.user.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract
