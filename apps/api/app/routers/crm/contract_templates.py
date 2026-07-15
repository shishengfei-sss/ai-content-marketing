"""合同模板 API（v1.0 P0）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_deals import (
    ContractTemplateCreate,
    ContractTemplateOut,
    ContractTemplateUpdate,
)
from app.services.crm.contract_template_service import (
    create_template,
    delete_template,
    get_template,
    list_templates,
    update_template,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/contract-templates", tags=["crm-contract-templates"])


@router.get("", response_model=list[ContractTemplateOut])
def get_templates(
    active_only: bool = Query(default=False),
    ctx: TenantContext = Depends(require_permission("crm.contract.view")),
    db: Session = Depends(get_db),
):
    return [
        ContractTemplateOut.model_validate(t)
        for t in list_templates(db, ctx.tenant_id, active_only=active_only)
    ]


@router.post("", response_model=ContractTemplateOut, status_code=201)
def post_template(
    body: ContractTemplateCreate,
    ctx: TenantContext = Depends(require_permission("crm.contract.create")),
    db: Session = Depends(get_db),
):
    tpl = create_template(db, ctx, body)
    return ContractTemplateOut.model_validate(tpl)


@router.patch("/{template_id}", response_model=ContractTemplateOut)
def patch_template(
    template_id: UUID,
    body: ContractTemplateUpdate,
    ctx: TenantContext = Depends(require_permission("crm.contract.edit")),
    db: Session = Depends(get_db),
):
    tpl = get_template(db, ctx.tenant_id, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="合同模板不存在")
    tpl = update_template(db, tpl, body)
    return ContractTemplateOut.model_validate(tpl)


@router.delete("/{template_id}", status_code=204)
def delete_template_endpoint(
    template_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.edit")),
    db: Session = Depends(get_db),
):
    tpl = get_template(db, ctx.tenant_id, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="合同模板不存在")
    delete_template(db, tpl)
