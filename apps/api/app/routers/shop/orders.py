"""商家端订单 A09。对照 PRD 01-管理端UI #a09。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import (
    MarkInvoiceRequest,
    OrderCloseRequest,
    OrderExportRequest,
    OrderListResponse,
    OrderOut,
    OrderRefundRequest,
    OrderResendNotifyRequest,
    RefundOut,
    ShopExportTaskOut,
)
from app.services.permission_service import require_permission
from app.services.shop import order_service

router = APIRouter(prefix="/orders", tags=["shop-orders"])


@router.get("", response_model=OrderListResponse)
def list_orders(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    source: str | None = Query(default=None, description="private|public_douyin|public_course_lib"),
    type: str | None = Query(default=None, alias="product_type"),
    amount_min: int | None = Query(default=None, ge=0),
    amount_max: int | None = Query(default=None, ge=0),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    external_order_no: str | None = Query(default=None),
    buyer_id: UUID | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ctx: TenantContext = Depends(require_permission("shop.order.list_all")),
    db: Session = Depends(get_db),
):
    items, total, counts = order_service.list_merchant_orders(
        db,
        ctx,
        status_filter=status,
        q=q,
        page=page,
        page_size=page_size,
        source=source,
        product_type=type,
        amount_min=amount_min,
        amount_max=amount_max,
        created_from=created_from,
        created_to=created_to,
        external_order_no=external_order_no,
        buyer_id=buyer_id,
        shop_id=shop_id,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return OrderListResponse(
        items=items, total=total, page=page, page_size=page_size, status_counts=counts
    )


_ORDER_EXPORT_PERM = require_permission(
    "shop.order.export", forbidden_detail="无订单导出权限"
)


@router.get("/export")
def export_orders(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    source: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    product_type: str | None = Query(default=None),
    amount_min: int | None = Query(default=None, ge=0),
    amount_max: int | None = Query(default=None, ge=0),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    external_order_no: str | None = Query(default=None),
    ctx: TenantContext = Depends(_ORDER_EXPORT_PERM),
    db: Session = Depends(get_db),
):
    csv_text = order_service.export_merchant_orders_csv(
        db,
        ctx,
        status_filter=status,
        q=q,
        source=source,
        shop_id=shop_id,
        product_type=product_type,
        amount_min=amount_min,
        amount_max=amount_max,
        created_from=created_from,
        created_to=created_to,
        external_order_no=external_order_no,
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-orders.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_export_task(
    body: OrderExportRequest | None = None,
    ctx: TenantContext = Depends(_ORDER_EXPORT_PERM),
    db: Session = Depends(get_db),
):
    return order_service.create_order_export_task(db, ctx, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_export_task(
    task_id: UUID,
    ctx: TenantContext = Depends(_ORDER_EXPORT_PERM),
    db: Session = Depends(get_db),
):
    return order_service.get_order_export_task(db, ctx, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_export_file(
    task_id: UUID,
    ctx: TenantContext = Depends(_ORDER_EXPORT_PERM),
    db: Session = Depends(get_db),
):
    csv_text = order_service.read_order_export_file(db, ctx, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-orders.csv"'},
    )


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.order.view")),
    db: Session = Depends(get_db),
):
    return order_service.get_merchant_order(db, ctx, order_id)


@router.post("/{order_id}/reveal-mobile", response_model=OrderOut)
def reveal_mobile(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.buyer.view")),
    db: Session = Depends(get_db),
):
    return order_service.reveal_order_mobile(db, ctx, order_id)


@router.post("/{order_id}/reveal-sensitive", response_model=OrderOut)
def reveal_sensitive(
    order_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.buyer.view")),
    db: Session = Depends(get_db),
):
    """PRD #a10-sensitive 别名 → reveal-mobile。"""
    return order_service.reveal_order_mobile(db, ctx, order_id)


@router.post("/{order_id}/close", response_model=OrderOut)
def close_order(
    order_id: UUID,
    body: OrderCloseRequest,
    ctx: TenantContext = Depends(require_permission("shop.order.close")),
    db: Session = Depends(get_db),
):
    return order_service.close_order(db, ctx, order_id, body.reason)


@router.post("/{order_id}/resend-notify")
def resend_notify(
    order_id: UUID,
    body: OrderResendNotifyRequest,
    ctx: TenantContext = Depends(require_permission("shop.order.resend_notify")),
    db: Session = Depends(get_db),
):
    return order_service.resend_claim_notify(db, ctx, order_id, body.remark)


@router.post("/{order_id}/refund", response_model=RefundOut)
def refund_order(
    order_id: UUID,
    body: OrderRefundRequest,
    ctx: TenantContext = Depends(require_permission("shop.order.refund")),
    db: Session = Depends(get_db),
):
    return order_service.merchant_refund(db, ctx, order_id, body)


@router.post("/{order_id}/mark-invoice", response_model=OrderOut)
def mark_invoice(
    order_id: UUID,
    body: MarkInvoiceRequest,
    ctx: TenantContext = Depends(require_permission("shop.order.view")),
    db: Session = Depends(get_db),
):
    return order_service.mark_invoice(db, ctx, order_id, body.invoice_status)
