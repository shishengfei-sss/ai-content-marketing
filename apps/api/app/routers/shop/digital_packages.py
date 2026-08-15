"""商家端 A06 资料包。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import (
    DigitalAssetCreateRequest,
    DigitalAssetOut,
    DigitalPackageCreateRequest,
    DigitalPackageExportRequest,
    DigitalPackageListResponse,
    DigitalPackageOut,
    DigitalPackagePatchRequest,
    ShopExportTaskOut,
)
from app.services.permission_service import require_permission
from app.services.shop import content_cms_service

router = APIRouter(prefix="/digital-packages", tags=["shop-digital-packages"])


@router.get("", response_model=DigitalPackageListResponse)
def list_packages(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    items, total, counts = content_cms_service.list_packages(
        db, ctx, page=page, page_size=page_size, status=status, q=q, shop_id=shop_id
    )
    return DigitalPackageListResponse(
        items=items, total=total, page=page, page_size=page_size, status_counts=counts
    )


@router.post("", response_model=DigitalPackageOut, status_code=201)
def create_package(
    body: DigitalPackageCreateRequest,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.create_package(db, ctx, body)


@router.get("/export")
def export_packages(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    csv_text = content_cms_service.export_packages_csv(
        db, ctx, status=status, q=q, shop_id=shop_id
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-digital-packages.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_package_export_task(
    body: DigitalPackageExportRequest | None = None,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    """对照 #a06 · 04#select-common：资料包列表异步导出（站内信本批不接）。"""
    return content_cms_service.create_package_export_task(db, ctx, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_package_export_task(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    return content_cms_service.get_package_export_task(db, ctx, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_package_export_file(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    csv_text = content_cms_service.read_package_export_file(db, ctx, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-digital-packages.csv"'},
    )


@router.get("/{package_id}", response_model=DigitalPackageOut)
def get_package(
    package_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    return content_cms_service.get_package(db, ctx, package_id)


@router.patch("/{package_id}", response_model=DigitalPackageOut)
def patch_package(
    package_id: UUID,
    body: DigitalPackagePatchRequest,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.patch_package(db, ctx, package_id, body)


@router.post("/{package_id}/publish", response_model=DigitalPackageOut)
def publish_package(
    package_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.publish_package(db, ctx, package_id)


@router.post("/{package_id}/off-sale", response_model=DigitalPackageOut)
def off_sale_package(
    package_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.off_sale_package(db, ctx, package_id)


@router.delete("/{package_id}")
def delete_package(
    package_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.delete_package(db, ctx, package_id)


@router.post("/{package_id}/assets", response_model=DigitalAssetOut, status_code=201)
def add_asset(
    package_id: UUID,
    body: DigitalAssetCreateRequest,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.add_asset(db, ctx, package_id, body)


@router.delete("/{package_id}/assets/{asset_id}")
def delete_asset(
    package_id: UUID,
    asset_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.delete_asset(db, ctx, package_id, asset_id)
