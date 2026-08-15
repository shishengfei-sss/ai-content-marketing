"""P04 平台类目与费率。对照 06-平台端UI.html #p04 · #p04d。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.shop_platform import (
    CategoryEnableApplicationListResponse,
    CategoryEnableApplicationOut,
    PlatformCategoryCreateRequest,
    PlatformCategoryDisableRequest,
    PlatformCategoryEnableRejectRequest,
    PlatformCategoryEnableRequest,
    PlatformCategoryListResponse,
    PlatformCategoryOut,
    PlatformCategoryPatchRequest,
    PlatformCategoryPreviewCodeRequest,
)
from app.services.permission_service import require_platform_shop_permission
from app.services.shop import category_service

router = APIRouter(prefix="/categories", tags=["platform-shop-categories"])


@router.get("", response_model=PlatformCategoryListResponse)
def list_categories(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    parent_id: UUID | None = Query(default=None),
    root_only: bool = Query(default=False),
    settlement_rule: str | None = Query(default=None),
    pending_enable: bool | None = Query(default=None),
    sort_by: str = Query(default="updated_at"),
    sort_dir: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    items, total = category_service.list_admin(
        db,
        status=status,
        q=q,
        parent_id=parent_id,
        root_only=root_only,
        settlement_rule=settlement_rule,
        pending_enable=pending_enable,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    return PlatformCategoryListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/preview-code")
def preview_code(
    body: PlatformCategoryPreviewCodeRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    return category_service.preview_code(db, parent_id=body.parent_id, name=body.name)


@router.get("/enable-applications", response_model=CategoryEnableApplicationListResponse)
def list_enable_applications(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    items, total = category_service.list_enable_applications(
        db, status=status, page=page, page_size=page_size
    )
    return CategoryEnableApplicationListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/enable-applications/{application_id}", response_model=CategoryEnableApplicationOut)
def get_enable_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    return category_service.get_enable_application(db, application_id)


@router.post(
    "/enable-applications/{application_id}/approve",
    response_model=CategoryEnableApplicationOut,
)
def approve_enable_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    return category_service.approve_enable_application(db, user, application_id)


@router.post(
    "/enable-applications/{application_id}/reject",
    response_model=CategoryEnableApplicationOut,
)
def reject_enable_application(
    application_id: UUID,
    body: PlatformCategoryEnableRejectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    return category_service.reject_enable_application(
        db, user, application_id, reject_reason=body.reject_reason
    )


@router.post("", response_model=PlatformCategoryOut)
def create_category(
    body: PlatformCategoryCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    return category_service.create_category(db, user, body)


@router.get("/{category_id}", response_model=PlatformCategoryOut)
def get_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    return category_service.get_category(db, category_id)


@router.patch("/{category_id}", response_model=PlatformCategoryOut)
def patch_category(
    category_id: UUID,
    body: PlatformCategoryPatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    return category_service.patch_category(db, user, category_id, body)


@router.post("/{category_id}/disable", response_model=PlatformCategoryOut)
def disable_category(
    category_id: UUID,
    body: PlatformCategoryDisableRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    return category_service.disable_category(
        db, user, category_id, reason_type=body.reason_type, reason=body.reason
    )


@router.post("/{category_id}/enable", response_model=CategoryEnableApplicationOut)
def enable_category(
    category_id: UUID,
    body: PlatformCategoryEnableRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.fee.manage")),
):
    """P04-D 提交启用审批（类目仍禁入，待通过后变启用）。"""
    return category_service.submit_enable_application(db, user, category_id, body)
