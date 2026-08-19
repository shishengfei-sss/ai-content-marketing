"""P09 商品人审。对照 PRD §8.8.3 · 06#p09 · #p09a · #p09b。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.shop_platform import (
    ProductApproveRequest,
    ProductForceOffRequest,
    ProductRejectRequest,
    ProductReviewListResponse,
    ProductReviewOut,
)
from app.services.permission_service import require_platform_shop_permission
from app.services.shop import product_service

router = APIRouter(prefix="/product-reviews", tags=["platform-shop-product-reviews"])


@router.get("", response_model=ProductReviewListResponse)
def list_reviews(
    status: str | None = Query(default="pending"),
    queue: str | None = Query(default=None, description="pending | flagged | reviewed"),
    q: str | None = Query(default=None),
    auto_result: str | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    product_status: str | None = Query(default=None),
    submitted_from: datetime | None = Query(default=None),
    submitted_to: datetime | None = Query(default=None),
    plan_label: str | None = Query(default=None),
    first_public: str | None = Query(default=None, description="yes | no"),
    sort_by: str | None = Query(default=None),
    sort_dir: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.product.review")),
):
    items, total, extra = product_service.list_product_reviews(
        db,
        status_filter=status,
        queue=queue,
        q=q,
        auto_result=auto_result,
        category_id=category_id,
        product_status=product_status,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
        plan_label=plan_label,
        first_public=(
            True if first_public == "yes" else False if first_public == "no" else None
        ),
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    return ProductReviewListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pending_count=extra["pending_count"],
        flagged_count=extra["flagged_count"],
        reviewed_count=extra["reviewed_count"],
        category_options=extra["category_options"],
    )


@router.get("/{review_id}", response_model=ProductReviewOut)
def get_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.product.review")),
):
    return product_service.get_product_review(db, review_id)


@router.get("/{review_id}/buyer-preview")
def get_buyer_preview(
    review_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.product.review")),
):
    return product_service.buyer_preview(db, review_id)


@router.get("/{review_id}/snapshot-cover")
def get_snapshot_cover(
    review_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.product.review")),
):
    return product_service.review_snapshot_cover(db, review_id)


@router.get("/{review_id}/lessons/{lesson_id}")
def get_review_lesson(
    review_id: UUID,
    lesson_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.product.review")),
):
    return product_service.review_lesson_detail(db, review_id, lesson_id)


@router.get("/{review_id}/lessons/{lesson_id}/media")
def get_review_lesson_media(
    review_id: UUID,
    lesson_id: UUID,
    download: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.product.review")),
):
    return product_service.review_lesson_media(db, review_id, lesson_id, download=download)


@router.get("/{review_id}/ref-assets/{file_id}")
def get_review_ref_asset(
    review_id: UUID,
    file_id: str,
    download: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.product.review")),
):
    return product_service.review_ref_asset(db, review_id, file_id, download=download)


@router.get("/{review_id}/ref-assets/{file_id}/html-preview", response_class=HTMLResponse)
def get_review_ref_asset_html_preview(
    review_id: UUID,
    file_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_shop_permission("platform.shop.product.review")),
):
    return product_service.review_ref_asset_html_preview(db, review_id, file_id)


@router.post("/{review_id}/approve", response_model=ProductReviewOut)
def approve_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.product.review")),
    body: ProductApproveRequest | None = None,
):
    return product_service.approve_review(db, user, review_id, note=(body.note if body else None))


@router.post("/{review_id}/reject", response_model=ProductReviewOut)
def reject_review(
    review_id: UUID,
    body: ProductRejectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.product.review")),
):
    return product_service.reject_review(db, user, review_id, body)


@router.post("/{review_id}/force-off-sale", response_model=ProductReviewOut)
def force_off_sale(
    review_id: UUID,
    body: ProductForceOffRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_shop_permission("platform.shop.product.force_off")),
):
    return product_service.force_off_from_review(db, user, review_id, body.reason)
