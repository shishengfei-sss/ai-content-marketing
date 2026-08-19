"""商家端商品 API（A02/A03）。对照 PRD §8.8。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import (
    ProductBatchRequest,
    ProductCreateRequest,
    ProductExportRequest,
    ProductListResponse,
    ProductOut,
    ProductPatchRequest,
    ProductSubmitReviewRequest,
    ShopExportTaskOut,
)
from app.services.permission_service import require_permission
from app.services.shop import product_service

router = APIRouter(prefix="/products", tags=["shop-products"])


def _parse_dt(v: str | None) -> datetime | None:
    if not v:
        return None
    s = v.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"invalid datetime: {v}") from e


@router.get("", response_model=ProductListResponse)
def list_products(
    shop_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    channel_mount: str | None = Query(default=None, description="mapped|none|rejected|pending"),
    price_min_cents: int | None = Query(default=None, ge=0),
    price_max_cents: int | None = Query(default=None, ge=0),
    updated_from: str | None = Query(default=None),
    updated_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ctx: TenantContext = Depends(require_permission("shop.product.read")),
    db: Session = Depends(get_db),
):
    items, total, status_counts = product_service.list_products(
        db,
        ctx,
        shop_id=shop_id,
        status_filter=status,
        type_filter=type,
        q=q,
        channel_mount=channel_mount,
        price_min_cents=price_min_cents,
        price_max_cents=price_max_cents,
        updated_from=_parse_dt(updated_from),
        updated_to=_parse_dt(updated_to),
        page=page,
        page_size=page_size,
    )
    return ProductListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        status_counts=status_counts,
    )


@router.get("/export")
def export_products(
    shop_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    channel_mount: str | None = Query(default=None),
    price_min_cents: int | None = Query(default=None, ge=0),
    price_max_cents: int | None = Query(default=None, ge=0),
    updated_from: str | None = Query(default=None),
    updated_to: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.product.read")),
    db: Session = Depends(get_db),
):
    csv_text = product_service.export_products_csv(
        db,
        ctx,
        shop_id=shop_id,
        status_filter=status,
        type_filter=type,
        q=q,
        channel_mount=channel_mount,
        price_min_cents=price_min_cents,
        price_max_cents=price_max_cents,
        updated_from=_parse_dt(updated_from),
        updated_to=_parse_dt(updated_to),
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-products.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_product_export_task(
    body: ProductExportRequest | None = None,
    ctx: TenantContext = Depends(require_permission("shop.product.read")),
    db: Session = Depends(get_db),
):
    """对照 #a02 · 04#select-common：商品列表异步导出（站内信本批不接）。"""
    return product_service.create_product_export_task(db, ctx, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_product_export_task(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.product.read")),
    db: Session = Depends(get_db),
):
    return product_service.get_product_export_task(db, ctx, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_product_export_file(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.product.read")),
    db: Session = Depends(get_db),
):
    csv_text = product_service.read_product_export_file(db, ctx, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-products.csv"'},
    )


@router.post("/batch-submit-review")
def batch_submit_review(
    body: ProductBatchRequest,
    ctx: TenantContext = Depends(require_permission("shop.product.submit_review")),
    db: Session = Depends(get_db),
):
    return product_service.batch_submit_review(db, ctx, body.product_ids)


@router.post("/batch-off-sale")
def batch_off_sale(
    body: ProductBatchRequest,
    ctx: TenantContext = Depends(require_permission("shop.product.publish")),
    db: Session = Depends(get_db),
):
    return product_service.batch_off_sale(db, ctx, body.product_ids)


@router.post("", response_model=ProductOut)
def create_product(
    body: ProductCreateRequest,
    ctx: TenantContext = Depends(require_permission("shop.product.write")),
    db: Session = Depends(get_db),
):
    return product_service.create_product(db, ctx, body)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.product.read")),
    db: Session = Depends(get_db),
):
    return product_service.get_product(db, ctx, product_id)


@router.get("/{product_id}/delete-precheck")
def delete_precheck(
    product_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.product.delete")),
    db: Session = Depends(get_db),
):
    return product_service.delete_precheck(db, ctx, product_id)


@router.patch("/{product_id}", response_model=ProductOut)
def patch_product(
    product_id: UUID,
    body: ProductPatchRequest,
    ctx: TenantContext = Depends(require_permission("shop.product.write")),
    db: Session = Depends(get_db),
):
    return product_service.patch_product(db, ctx, product_id, body)


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.product.delete")),
    db: Session = Depends(get_db),
):
    product_service.soft_delete_product(db, ctx, product_id)
    return None


@router.post("/{product_id}/submit-review")
def submit_review(
    product_id: UUID,
    body: ProductSubmitReviewRequest | None = None,
    ctx: TenantContext = Depends(require_permission("shop.product.submit_review")),
    db: Session = Depends(get_db),
):
    return product_service.submit_review(db, ctx, product_id, (body.remark if body else None))


@router.post("/{product_id}/withdraw", response_model=ProductOut)
def withdraw_product(
    product_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.product.write")),
    db: Session = Depends(get_db),
):
    return product_service.withdraw_product(db, ctx, product_id)


@router.post("/{product_id}/publish", response_model=ProductOut)
def publish_product(
    product_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.product.publish")),
    db: Session = Depends(get_db),
):
    return product_service.publish_product(db, ctx, product_id)


@router.post("/{product_id}/off-sale", response_model=ProductOut)
def off_sale_product(
    product_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.product.publish")),
    db: Session = Depends(get_db),
):
    return product_service.off_sale_product(db, ctx, product_id)
