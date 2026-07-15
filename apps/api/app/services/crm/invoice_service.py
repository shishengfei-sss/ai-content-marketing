"""发票服务（v1.0 P1）。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models.crm import Invoice, InvoicePayment, Payment
from app.schemas.crm_deals import InvoiceCreate, InvoicePaymentCreate, InvoiceUpdate
from app.services.crm.number_service import generate_number
from app.services.crm.order_service import require_order


def get_invoice(db: Session, tenant_id: UUID, invoice_id: UUID) -> Invoice | None:
    return (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id, Invoice.deleted_at.is_(None))
        .first()
    )


def require_invoice(db: Session, ctx: TenantContext, invoice_id: UUID) -> Invoice:
    inv = get_invoice(db, ctx.tenant_id, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    require_order(db, ctx, inv.order_id)
    return inv


def list_order_invoices(db: Session, ctx: TenantContext, order_id: UUID) -> list[Invoice]:
    require_order(db, ctx, order_id)
    return (
        db.query(Invoice)
        .filter(
            Invoice.tenant_id == ctx.tenant_id,
            Invoice.order_id == order_id,
            Invoice.deleted_at.is_(None),
        )
        .order_by(Invoice.created_at.desc())
        .all()
    )


def create_invoice(db: Session, ctx: TenantContext, order_id: UUID, data: InvoiceCreate) -> Invoice:
    order = require_order(db, ctx, order_id)
    if order.status in ("draft", "pending_approval", "rejected", "cancelled", "superseded"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"订单状态为 {order.status}，不可开票",
        )
    total = data.total_amount
    if total is None:
        total = round(float(data.amount) + float(data.tax_amount), 2)
    inv = Invoice(
        tenant_id=ctx.tenant_id,
        order_id=order.id,
        invoice_number=generate_number(db, ctx.tenant_id, "invoice"),
        invoice_type=data.invoice_type,
        amount=data.amount,
        tax_amount=data.tax_amount,
        total_amount=total,
        status="draft",
        extra_data=data.extra_data or {},
        created_by_user_id=ctx.user.id,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def update_invoice(db: Session, ctx: TenantContext, inv: Invoice, data: InvoiceUpdate) -> Invoice:
    if inv.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="仅草稿发票可编辑")
    if data.invoice_type is not None:
        inv.invoice_type = data.invoice_type
    if data.amount is not None:
        inv.amount = data.amount
    if data.tax_amount is not None:
        inv.tax_amount = data.tax_amount
    if data.total_amount is not None:
        inv.total_amount = data.total_amount
    elif data.amount is not None or data.tax_amount is not None:
        inv.total_amount = round(float(inv.amount) + float(inv.tax_amount), 2)
    if data.extra_data is not None:
        inv.extra_data = data.extra_data
    db.commit()
    db.refresh(inv)
    return inv


def issue_invoice(db: Session, ctx: TenantContext, inv: Invoice) -> Invoice:
    if inv.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"发票状态为 {inv.status}，不可开具")
    inv.status = "issued"
    inv.issued_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(inv)
    return inv


def void_invoice(db: Session, ctx: TenantContext, inv: Invoice) -> Invoice:
    if inv.status == "void":
        return inv
    if inv.status not in ("draft", "issued"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"发票状态为 {inv.status}，不可作废")
    inv.status = "void"
    db.commit()
    db.refresh(inv)
    return inv


def match_invoice_payment(
    db: Session, ctx: TenantContext, inv: Invoice, data: InvoicePaymentCreate
) -> InvoicePayment:
    if inv.status != "issued":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="仅已开具发票可核销回款")
    pay = (
        db.query(Payment)
        .filter(Payment.id == data.payment_id, Payment.tenant_id == ctx.tenant_id)
        .first()
    )
    if not pay:
        raise HTTPException(status_code=404, detail="回款不存在")
    if pay.order_id != inv.order_id:
        raise HTTPException(status_code=400, detail="回款与发票须属于同一订单")
    exists = (
        db.query(InvoicePayment)
        .filter(InvoicePayment.invoice_id == inv.id, InvoicePayment.payment_id == pay.id)
        .first()
    )
    if exists:
        exists.matched_amount = data.matched_amount
        db.commit()
        db.refresh(exists)
        return exists
    link = InvoicePayment(
        invoice_id=inv.id,
        payment_id=pay.id,
        matched_amount=data.matched_amount,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def list_invoice_payments(db: Session, ctx: TenantContext, inv: Invoice) -> list[InvoicePayment]:
    require_order(db, ctx, inv.order_id)
    return db.query(InvoicePayment).filter(InvoicePayment.invoice_id == inv.id).all()
