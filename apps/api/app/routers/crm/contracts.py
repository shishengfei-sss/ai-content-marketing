"""合同 API（v0.7 + 状态机/审批/批量/复制增强）。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.models.crm import Contract
from app.schemas.crm_deals import (
    ContractAmendmentCreate,
    ContractAmendmentOut,
    ContractBatchAction,
    ContractBatchActionResult,
    ContractConvertToOrderOut,
    ContractCreate,
    ContractFromTemplateRequest,
    ContractListResponse,
    ContractOut,
    ContractRejectBody,
    ContractRenewOut,
    ContractUpdate,
)
from app.services.crm.contract_amendment_service import (
    approve_amendment,
    create_amendment,
    execute_amendment,
    get_amendment,
    list_amendments,
)
from app.services.crm.contract_expiry_job import create_renewal_deal_for_contract
from app.services.crm.contract_service import (
    activate_contract,
    approve_contract,
    batch_contract_action,
    clone_contract,
    contract_to_out,
    convert_contract_to_order,
    create_contract,
    reject_contract,
    renew_as_contract,
    require_contract,
    send_contract,
    sign_contract,
    soft_delete_contract,
    submit_contract,
    terminate_contract,
    update_contract,
    withdraw_contract,
)
from app.services.crm.contract_template_service import create_contract_from_template
from app.services.crm.crm_scope_service import apply_contract_list_scope, has_contract_list_permission
from app.services.crm.filter_query import parse_list_filters_param
from app.services.crm.view_service import (
    apply_view_filters,
    apply_view_search,
    apply_view_sort,
    assert_can_access_view,
    get_view,
    resolve_view_list_columns,
)
from app.services.permission_service import require_any_permission, require_permission

router = APIRouter(prefix="/contracts", tags=["crm-contracts"])


class ContractSignBody(BaseModel):
    signed_amount: float | None = None
    signed_at: datetime | None = None


@router.get("", response_model=ContractListResponse)
def list_contracts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    view_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),
    deal_id: UUID | None = Query(default=None),
    filters: str | None = Query(default=None, description="高级筛选 JSON"),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None, pattern="^(asc|desc)$"),
    ctx: TenantContext = Depends(
        require_any_permission("crm.contract.list_own", "crm.contract.list_team", "crm.contract.list_all")
    ),
    db: Session = Depends(get_db),
):
    if not has_contract_list_permission(ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")

    active_view = None
    filters_applied = False
    if view_id is not None:
        active_view = get_view(db, ctx.tenant_id, view_id)
        if not active_view:
            raise HTTPException(status_code=404, detail="视图不存在")
        assert_can_access_view(ctx, active_view)

    query = db.query(Contract).filter(Contract.tenant_id == ctx.tenant_id, Contract.deleted_at.is_(None))
    query = apply_contract_list_scope(query, ctx, db)

    if active_view:
        query = apply_view_filters(query, db, ctx.tenant_id, "contract", active_view.filters)
        query = apply_view_search(query, "contract", active_view.search_q)
        query = apply_view_sort(query, "contract", active_view.sort)
    else:
        parsed_filters = parse_list_filters_param(filters)
        if parsed_filters and parsed_filters.get("conditions"):
            query = apply_view_filters(query, db, ctx.tenant_id, "contract", parsed_filters)
            filters_applied = True
        elif status:
            query = query.filter(Contract.status == status)
        query = apply_view_search(query, "contract", q)
        sort_spec = None
        if sort_by:
            sort_spec = [{"field_key": sort_by, "dir": (sort_dir or "desc").lower()}]
        query = apply_view_sort(query, "contract", sort_spec)

    if customer_id is not None:
        query = query.filter(Contract.customer_id == customer_id)
    if deal_id is not None:
        query = query.filter(Contract.deal_id == deal_id)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return ContractListResponse(
        items=[contract_to_out(db, i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        list_fields=resolve_view_list_columns(db, ctx.tenant_id, ctx.user.id, "contract", active_view),
        view_id=active_view.id if active_view else None,
        filters_applied=filters_applied if filters else None,
    )


@router.post("/batch-action", response_model=ContractBatchActionResult)
def batch_contracts_endpoint(
    body: ContractBatchAction,
    ctx: TenantContext = Depends(require_any_permission("crm.contract.sign", "crm.contract.edit")),
    db: Session = Depends(get_db),
):
    return batch_contract_action(db, ctx, body)


@router.post("", response_model=ContractOut, status_code=201)
def post_contract(
    body: ContractCreate,
    ctx: TenantContext = Depends(require_permission("crm.contract.create")),
    db: Session = Depends(get_db),
):
    c = create_contract(db, ctx, body)
    return contract_to_out(db, c)


@router.post("/from-template", response_model=ContractOut, status_code=201)
def post_contract_from_template(
    body: ContractFromTemplateRequest,
    ctx: TenantContext = Depends(require_permission("crm.contract.create")),
    db: Session = Depends(get_db),
):
    c = create_contract_from_template(db, ctx, body)
    return contract_to_out(db, c)


@router.get("/{contract_id}", response_model=ContractOut)
def get_contract_detail(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.view")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    return contract_to_out(db, c)


@router.patch("/{contract_id}", response_model=ContractOut)
def patch_contract(
    contract_id: UUID,
    body: ContractUpdate,
    ctx: TenantContext = Depends(require_permission("crm.contract.edit")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    c = update_contract(db, ctx, c, body)
    return contract_to_out(db, c)


@router.post("/{contract_id}/send", response_model=ContractOut)
def send_contract_endpoint(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.edit")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    c = send_contract(db, ctx, c)
    return contract_to_out(db, c)


@router.post("/{contract_id}/submit", response_model=ContractOut)
def submit_contract_endpoint(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.sign")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    c = submit_contract(db, ctx, c)
    return contract_to_out(db, c)


@router.post("/{contract_id}/approve", response_model=ContractOut)
def approve_contract_endpoint(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.approve")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    c = approve_contract(db, ctx, c)
    return contract_to_out(db, c)


@router.post("/{contract_id}/reject", response_model=ContractOut)
def reject_contract_endpoint(
    contract_id: UUID,
    body: ContractRejectBody,
    ctx: TenantContext = Depends(require_permission("crm.contract.approve")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    c = reject_contract(db, ctx, c, body.reason)
    return contract_to_out(db, c)


@router.post("/{contract_id}/withdraw", response_model=ContractOut)
def withdraw_contract_endpoint(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.sign")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    c = withdraw_contract(db, ctx, c)
    return contract_to_out(db, c)


@router.post("/{contract_id}/sign", response_model=ContractOut)
def sign_contract_endpoint(
    contract_id: UUID,
    body: ContractSignBody,
    ctx: TenantContext = Depends(require_permission("crm.contract.sign")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    c = sign_contract(db, ctx, c, signed_amount=body.signed_amount, signed_at=body.signed_at)
    return contract_to_out(db, c)


@router.post("/{contract_id}/activate", response_model=ContractOut)
def activate_contract_endpoint(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.edit")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    c = activate_contract(db, ctx, c)
    return contract_to_out(db, c)


@router.post("/{contract_id}/terminate", response_model=ContractOut)
def terminate_contract_endpoint(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.edit")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    c = terminate_contract(db, ctx, c)
    return contract_to_out(db, c)


@router.post("/{contract_id}/clone", response_model=ContractOut, status_code=201)
def clone_contract_endpoint(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.create")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    cloned = clone_contract(db, ctx, c)
    return contract_to_out(db, cloned)


@router.post("/{contract_id}/renew-contract", response_model=ContractOut, status_code=201)
def renew_as_contract_endpoint(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.create")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    renewed = renew_as_contract(db, ctx, c)
    return contract_to_out(db, renewed)


@router.post("/{contract_id}/convert-to-order", response_model=ContractConvertToOrderOut, status_code=201)
def convert_contract_to_order_endpoint(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.convert")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    order = convert_contract_to_order(db, ctx, c)
    return ContractConvertToOrderOut(contract_id=c.id, order_id=order.id)


@router.post("/{contract_id}/renew", response_model=ContractRenewOut, status_code=201)
def renew_contract_endpoint(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.deal.create")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    deal = create_renewal_deal_for_contract(db, c)
    if not deal:
        raise HTTPException(status_code=409, detail="续约商机已存在或创建失败")
    db.commit()
    return ContractRenewOut(contract_id=c.id, deal_id=deal.id)


@router.get("/{contract_id}/amendments", response_model=list[ContractAmendmentOut])
def list_amendments_endpoint(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.view")),
    db: Session = Depends(get_db),
):
    items = list_amendments(db, ctx, contract_id)
    return [ContractAmendmentOut.model_validate(i) for i in items]


@router.post("/{contract_id}/amendments", response_model=ContractAmendmentOut, status_code=201)
def create_amendment_endpoint(
    contract_id: UUID,
    body: ContractAmendmentCreate,
    ctx: TenantContext = Depends(require_permission("crm.contract.edit")),
    db: Session = Depends(get_db),
):
    row = create_amendment(db, ctx, contract_id, body)
    return ContractAmendmentOut.model_validate(row)


@router.post("/amendments/{amendment_id}/approve", response_model=ContractAmendmentOut)
def approve_amendment_endpoint(
    amendment_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.edit")),
    db: Session = Depends(get_db),
):
    row = get_amendment(db, ctx.tenant_id, amendment_id)
    if not row:
        raise HTTPException(status_code=404, detail="补充协议不存在")
    row = approve_amendment(db, ctx, row)
    return ContractAmendmentOut.model_validate(row)


@router.post("/amendments/{amendment_id}/execute", response_model=ContractAmendmentOut)
def execute_amendment_endpoint(
    amendment_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.edit")),
    db: Session = Depends(get_db),
):
    row = get_amendment(db, ctx.tenant_id, amendment_id)
    if not row:
        raise HTTPException(status_code=404, detail="补充协议不存在")
    row = execute_amendment(db, ctx, row)
    return ContractAmendmentOut.model_validate(row)


@router.delete("/{contract_id}", status_code=204)
def delete_contract_endpoint(
    contract_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.contract.delete")),
    db: Session = Depends(get_db),
):
    c = require_contract(db, ctx, contract_id)
    soft_delete_contract(db, ctx, c)
