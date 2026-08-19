"""买家已购权益 · 学课/资料履约。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies_shop_buyer import BuyerContext, get_buyer_context
from app.schemas.shop_platform import (
    CourseOutlineOut,
    EntitlementListResponse,
    EntitlementOut,
    LessonProgressOut,
    LessonProgressUpsertRequest,
    MaterialDownloadOut,
    MaterialsOut,
)
from app.services.shop import content_fulfillment_service, fulfillment_service, order_service

router = APIRouter(prefix="/entitlements", tags=["mp-shop-entitlements"])


@router.get("", response_model=EntitlementListResponse)
def list_mine(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    items, total = order_service.list_entitlements_buyer(
        db, bctx.buyer, page=page, page_size=page_size
    )
    return EntitlementListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{entitlement_id}/assert-active", response_model=EntitlementOut)
def assert_active(
    entitlement_id: UUID,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return order_service.assert_entitlement_active(db, entitlement_id, buyer_id=bctx.buyer.id)


@router.get("/{entitlement_id}/outline", response_model=CourseOutlineOut)
def course_outline(
    entitlement_id: UUID,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return content_fulfillment_service.get_course_outline(db, bctx.buyer, entitlement_id)


@router.get("/{entitlement_id}/lessons/{lesson_id}/media")
def lesson_media(
    entitlement_id: UUID,
    lesson_id: UUID,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    path, media_type, filename = content_fulfillment_service.stream_lesson_media(
        db, bctx.buyer, entitlement_id, lesson_id
    )
    return FileResponse(path, filename=filename, media_type=_media_mime(media_type, filename))


def _media_mime(media_type: str, filename: str) -> str:
    name = (filename or "").lower()
    if media_type == "audio" or name.endswith((".mp3", ".m4a", ".wav", ".aac")):
        return "audio/mpeg"
    if name.endswith(".webm"):
        return "video/webm"
    return "video/mp4"


@router.get("/{entitlement_id}/materials", response_model=MaterialsOut)
def materials(
    entitlement_id: UUID,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return content_fulfillment_service.get_materials(db, bctx.buyer, entitlement_id)


@router.post(
    "/{entitlement_id}/materials/{file_id}/download",
    response_model=MaterialDownloadOut,
)
def download_material(
    entitlement_id: UUID,
    file_id: str,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return content_fulfillment_service.download_material(
        db, bctx.buyer, entitlement_id, file_id
    )


@router.put(
    "/{entitlement_id}/lessons/{lesson_id}/progress",
    response_model=LessonProgressOut,
)
def upsert_lesson_progress(
    entitlement_id: UUID,
    lesson_id: UUID,
    body: LessonProgressUpsertRequest,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return fulfillment_service.upsert_lesson_progress(
        db, bctx.buyer, entitlement_id, lesson_id, body
    )


@router.get(
    "/{entitlement_id}/lessons/{lesson_id}/progress",
    response_model=LessonProgressOut,
)
def get_lesson_progress(
    entitlement_id: UUID,
    lesson_id: UUID,
    bctx: BuyerContext = Depends(get_buyer_context),
    db: Session = Depends(get_db),
):
    return fulfillment_service.get_lesson_progress(db, bctx.buyer, entitlement_id, lesson_id)
