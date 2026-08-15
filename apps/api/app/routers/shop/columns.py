"""商家端 A04/A05 专栏与课时。"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import (
    ColumnCreateRequest,
    ColumnExportRequest,
    ColumnListResponse,
    ColumnOut,
    ColumnPatchRequest,
    LessonCreateRequest,
    LessonListResponse,
    LessonOut,
    LessonPatchRequest,
    ShopExportTaskOut,
)
from app.services.permission_service import require_permission
from app.services.shop import content_cms_service

router = APIRouter(prefix="/columns", tags=["shop-columns"])


@router.get("", response_model=ColumnListResponse)
def list_columns(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    ref_min: int | None = Query(default=None, ge=0),
    ref_max: int | None = Query(default=None, ge=0),
    updated_from: date | None = Query(default=None),
    updated_to: date | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    items, total, counts = content_cms_service.list_columns(
        db,
        ctx,
        page=page,
        page_size=page_size,
        status=status,
        q=q,
        shop_id=shop_id,
        ref_min=ref_min,
        ref_max=ref_max,
        updated_from=updated_from,
        updated_to=updated_to,
    )
    return ColumnListResponse(
        items=items, total=total, page=page, page_size=page_size, status_counts=counts
    )


@router.post("", response_model=ColumnOut, status_code=201)
def create_column(
    body: ColumnCreateRequest,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.create_column(db, ctx, body)


@router.get("/export")
def export_columns(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    ref_min: int | None = Query(default=None, ge=0),
    ref_max: int | None = Query(default=None, ge=0),
    updated_from: date | None = Query(default=None),
    updated_to: date | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    csv_text = content_cms_service.export_columns_csv(
        db,
        ctx,
        status=status,
        q=q,
        shop_id=shop_id,
        ref_min=ref_min,
        ref_max=ref_max,
        updated_from=updated_from,
        updated_to=updated_to,
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-columns.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_column_export_task(
    body: ColumnExportRequest | None = None,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    """对照 #a04 · 04#select-common：专栏列表异步导出（站内信本批不接）。"""
    return content_cms_service.create_column_export_task(db, ctx, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_column_export_task(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    return content_cms_service.get_column_export_task(db, ctx, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_column_export_file(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    csv_text = content_cms_service.read_column_export_file(db, ctx, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-columns.csv"'},
    )


@router.get("/{column_id}", response_model=ColumnOut)
def get_column(
    column_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    return content_cms_service.get_column(db, ctx, column_id)


@router.patch("/{column_id}", response_model=ColumnOut)
def patch_column(
    column_id: UUID,
    body: ColumnPatchRequest,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.patch_column(db, ctx, column_id, body)


@router.post("/{column_id}/publish", response_model=ColumnOut)
def publish_column(
    column_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.publish_column(db, ctx, column_id)


@router.post("/{column_id}/off-sale", response_model=ColumnOut)
def off_sale_column(
    column_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.off_sale_column(db, ctx, column_id)


@router.delete("/{column_id}")
def delete_column(
    column_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.delete_column(db, ctx, column_id)


@router.get("/{column_id}/lessons", response_model=LessonListResponse)
def list_lessons(
    column_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    items, total = content_cms_service.list_lessons(db, ctx, column_id)
    return LessonListResponse(items=items, total=total)


@router.post("/{column_id}/lessons", response_model=LessonOut, status_code=201)
def create_lesson(
    column_id: UUID,
    body: LessonCreateRequest,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.create_lesson(db, ctx, column_id, body)


@router.patch("/{column_id}/lessons/{lesson_id}", response_model=LessonOut)
def patch_lesson(
    column_id: UUID,
    lesson_id: UUID,
    body: LessonPatchRequest,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.patch_lesson(db, ctx, column_id, lesson_id, body)


@router.post("/{column_id}/lessons/{lesson_id}/publish", response_model=LessonOut)
def publish_lesson(
    column_id: UUID,
    lesson_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.publish_lesson(db, ctx, column_id, lesson_id)


@router.post("/{column_id}/lessons/{lesson_id}/off-sale", response_model=LessonOut)
def off_sale_lesson(
    column_id: UUID,
    lesson_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.off_sale_lesson(db, ctx, column_id, lesson_id)


@router.delete("/{column_id}/lessons/{lesson_id}")
def delete_lesson(
    column_id: UUID,
    lesson_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.delete_lesson(db, ctx, column_id, lesson_id)
