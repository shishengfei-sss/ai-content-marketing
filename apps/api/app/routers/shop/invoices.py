"""商家端发票管理。对照 PRD 01-管理端UI.html #a13。"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import (
    InvoiceExportRequest,
    InvoiceExportTaskOut,
    InvoiceIssueRequest,
    InvoiceListResponse,
    InvoiceOut,
    InvoiceRejectRequest,
)
from app.services.permission_service import require_permission
from app.services.shop import fulfillment_service

router = APIRouter(prefix="/invoices", tags=["shop-invoices"])


@router.get("/export")
def export_csv(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    title_type: str | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.invoice.view")),
    db: Session = Depends(get_db),
):
    csv = fulfillment_service.export_invoices_csv(
        db,
        ctx,
        status=status,
        q=q,
        shop_id=shop_id,
        title_type=title_type,
        created_from=created_from,
        created_to=created_to,
    )
    return PlainTextResponse(
        csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=invoices.csv"},
    )


@router.post("/export", response_model=InvoiceExportTaskOut)
def create_export_task(
    body: InvoiceExportRequest | None = None,
    ctx: TenantContext = Depends(require_permission("shop.invoice.view")),
    db: Session = Depends(get_db),
):
    return fulfillment_service.create_invoice_export_task(db, ctx, body)


@router.get("/export-tasks/{task_id}", response_model=InvoiceExportTaskOut)
def get_export_task(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.invoice.view")),
    db: Session = Depends(get_db),
):
    return fulfillment_service.get_invoice_export_task(db, ctx, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_export_file(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.invoice.view")),
    db: Session = Depends(get_db),
):
    csv = fulfillment_service.read_invoice_export_file(db, ctx, task_id)
    return PlainTextResponse(
        csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=invoices.csv"},
    )


@router.get("", response_model=InvoiceListResponse)
def list_invoices(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    buyer_id: UUID | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    title_type: str | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.invoice.list_all")),
    db: Session = Depends(get_db),
):
    items, total, counts = fulfillment_service.list_invoices_merchant(
        db,
        ctx,
        page=page,
        page_size=page_size,
        status=status,
        q=q,
        buyer_id=buyer_id,
        shop_id=shop_id,
        title_type=title_type,
        created_from=created_from,
        created_to=created_to,
    )
    return InvoiceListResponse(
        items=items, total=total, page=page, page_size=page_size, status_counts=counts
    )


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.invoice.view")),
    db: Session = Depends(get_db),
):
    return fulfillment_service.get_invoice_merchant(db, ctx, invoice_id)


@router.post("/{invoice_id}/issue", response_model=InvoiceOut)
def issue(
    invoice_id: UUID,
    body: InvoiceIssueRequest,
    ctx: TenantContext = Depends(require_permission("shop.invoice.process")),
    db: Session = Depends(get_db),
):
    return fulfillment_service.issue_invoice(db, ctx, invoice_id, body)


@router.post("/{invoice_id}/reject", response_model=InvoiceOut)
def reject(
    invoice_id: UUID,
    body: InvoiceRejectRequest,
    ctx: TenantContext = Depends(require_permission("shop.invoice.process")),
    db: Session = Depends(get_db),
):
    return fulfillment_service.reject_invoice(db, ctx, invoice_id, body)
