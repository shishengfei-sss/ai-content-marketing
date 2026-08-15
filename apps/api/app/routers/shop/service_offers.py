"""商家端 A07 服务定义与时段。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import (
    BookingOut,
    ServiceOfferCreateRequest,
    ServiceOfferExportRequest,
    ServiceOfferListResponse,
    ServiceOfferOut,
    ServiceOfferPatchRequest,
    ServiceSlotBatchPreviewOut,
    ServiceSlotBatchRequest,
    ServiceSlotListResponse,
    ServiceSlotOut,
    ShopExportTaskOut,
)
from app.services.permission_service import require_permission
from app.services.shop import service_offer_service

router = APIRouter(prefix="/service-offers", tags=["shop-service-offers"])


@router.get("", response_model=ServiceOfferListResponse)
def list_offers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    mode: str | None = Query(default=None),
    q: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    items, total, counts = service_offer_service.list_offers(
        db, ctx, page=page, page_size=page_size, status=status, mode=mode, q=q, shop_id=shop_id
    )
    return ServiceOfferListResponse(
        items=items, total=total, page=page, page_size=page_size, status_counts=counts
    )


@router.post("", response_model=ServiceOfferOut, status_code=201)
def create_offer(
    body: ServiceOfferCreateRequest,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return service_offer_service.create_offer(db, ctx, body)


@router.get("/export")
def export_offers(
    status: str | None = Query(default=None),
    mode: str | None = Query(default=None),
    q: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    csv_text = service_offer_service.export_offers_csv(
        db, ctx, status=status, mode=mode, q=q, shop_id=shop_id
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-service-offers.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_offer_export_task(
    body: ServiceOfferExportRequest | None = None,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    """对照 #a07 · 04#select-common：服务列表异步导出（站内信本批不接）。"""
    return service_offer_service.create_offer_export_task(db, ctx, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_offer_export_task(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    return service_offer_service.get_offer_export_task(db, ctx, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_offer_export_file(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    csv_text = service_offer_service.read_offer_export_file(db, ctx, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-service-offers.csv"'},
    )


@router.get("/{offer_id}", response_model=ServiceOfferOut)
def get_offer(
    offer_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    return service_offer_service.get_offer(db, ctx, offer_id)


@router.patch("/{offer_id}", response_model=ServiceOfferOut)
def patch_offer(
    offer_id: UUID,
    body: ServiceOfferPatchRequest,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return service_offer_service.patch_offer(db, ctx, offer_id, body)


@router.post("/{offer_id}/publish", response_model=ServiceOfferOut)
def publish_offer(
    offer_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return service_offer_service.publish_offer(db, ctx, offer_id)


@router.post("/{offer_id}/off-sale", response_model=ServiceOfferOut)
def off_sale_offer(
    offer_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return service_offer_service.off_sale_offer(db, ctx, offer_id)


@router.delete("/{offer_id}")
def delete_offer(
    offer_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return service_offer_service.delete_offer(db, ctx, offer_id)


@router.get("/{offer_id}/slots", response_model=ServiceSlotListResponse)
def list_slots(
    offer_id: UUID,
    status: str | None = Query(default=None),
    view: str | None = Query(default=None, pattern="^(upcoming|past)$"),
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    items, total = service_offer_service.list_slots_merchant(
        db, ctx, offer_id, status=status, view=view
    )
    return ServiceSlotListResponse(items=items, total=total)


@router.post("/{offer_id}/slots/batch-preview", response_model=ServiceSlotBatchPreviewOut)
def batch_preview(
    offer_id: UUID,
    body: ServiceSlotBatchRequest,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return service_offer_service.preview_batch_slots(db, ctx, offer_id, body)


@router.post("/{offer_id}/slots/batch", response_model=ServiceSlotListResponse)
def batch_create(
    offer_id: UUID,
    body: ServiceSlotBatchRequest,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return service_offer_service.create_batch_slots(db, ctx, offer_id, body)


@router.post("/{offer_id}/slots/{slot_id}/close", response_model=ServiceSlotOut)
def close_slot(
    offer_id: UUID,
    slot_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return service_offer_service.close_slot(db, ctx, offer_id, slot_id)


@router.get("/{offer_id}/slots/{slot_id}/bookings", response_model=list[BookingOut])
def slot_bookings(
    offer_id: UUID,
    slot_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    return service_offer_service.list_slot_bookings(db, ctx, offer_id, slot_id)
