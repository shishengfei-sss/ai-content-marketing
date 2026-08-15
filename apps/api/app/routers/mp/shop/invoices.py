"""买家端发票申请 M13。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies_shop_buyer import BuyerContext, get_buyer_context
from app.schemas.shop_platform import InvoiceCreateRequest, InvoiceListResponse, InvoiceOut
from app.services.shop import fulfillment_service

router = APIRouter(prefix="/invoices", tags=["mp-shop-invoices"])


@router.post("", response_model=InvoiceOut)
def create(
    body: InvoiceCreateRequest,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return fulfillment_service.create_invoice(db, bctx.buyer, body)


@router.get("", response_model=InvoiceListResponse)
def list_mine(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    items, total = fulfillment_service.list_invoices_buyer(
        db, bctx.buyer, page=page, page_size=page_size
    )
    return InvoiceListResponse(items=items, total=total, page=page, page_size=page_size)
