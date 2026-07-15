"""发票独立操作 API。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm_deals import (
    InvoiceOut,
    InvoicePaymentCreate,
    InvoicePaymentOut,
    InvoiceUpdate,
)
from app.services.crm.invoice_service import (
    issue_invoice,
    list_invoice_payments,
    match_invoice_payment,
    require_invoice,
    update_invoice,
    void_invoice,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/invoices", tags=["crm-invoices"])


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice_endpoint(
    invoice_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.view")),
    db: Session = Depends(get_db),
):
    inv = require_invoice(db, ctx, invoice_id)
    return InvoiceOut.model_validate(inv)


@router.patch("/{invoice_id}", response_model=InvoiceOut)
def patch_invoice_endpoint(
    invoice_id: UUID,
    body: InvoiceUpdate,
    ctx: TenantContext = Depends(require_permission("crm.order.edit")),
    db: Session = Depends(get_db),
):
    inv = require_invoice(db, ctx, invoice_id)
    inv = update_invoice(db, ctx, inv, body)
    return InvoiceOut.model_validate(inv)


@router.post("/{invoice_id}/issue", response_model=InvoiceOut)
def issue_invoice_endpoint(
    invoice_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.edit")),
    db: Session = Depends(get_db),
):
    inv = require_invoice(db, ctx, invoice_id)
    inv = issue_invoice(db, ctx, inv)
    return InvoiceOut.model_validate(inv)


@router.post("/{invoice_id}/void", response_model=InvoiceOut)
def void_invoice_endpoint(
    invoice_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.edit")),
    db: Session = Depends(get_db),
):
    inv = require_invoice(db, ctx, invoice_id)
    inv = void_invoice(db, ctx, inv)
    return InvoiceOut.model_validate(inv)


@router.get("/{invoice_id}/payments", response_model=list[InvoicePaymentOut])
def list_invoice_payments_endpoint(
    invoice_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.order.view")),
    db: Session = Depends(get_db),
):
    inv = require_invoice(db, ctx, invoice_id)
    items = list_invoice_payments(db, ctx, inv)
    return [InvoicePaymentOut.model_validate(i) for i in items]


@router.post("/{invoice_id}/payments", response_model=InvoicePaymentOut, status_code=201)
def match_invoice_payment_endpoint(
    invoice_id: UUID,
    body: InvoicePaymentCreate,
    ctx: TenantContext = Depends(require_permission("crm.order.edit")),
    db: Session = Depends(get_db),
):
    inv = require_invoice(db, ctx, invoice_id)
    link = match_invoice_payment(db, ctx, inv, body)
    return InvoicePaymentOut.model_validate(link)
