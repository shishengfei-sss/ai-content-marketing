"""买家店首页。对照 PRD §8.12.2 M02。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.shop_platform import MpStorefrontResponse
from app.services.shop import storefront_service

router = APIRouter(tags=["mp-shop-storefront"])


@router.get("/store", response_model=MpStorefrontResponse)
def get_store(
    shop_id: UUID = Query(..., description="店铺 ID"),
    q: str | None = Query(default=None, description="搜索关键词"),
    type: str | None = Query(default=None, description="course|digital|service"),
    sort: str = Query(default="default", description="default|price_asc|price_desc|sales"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return storefront_service.get_storefront(
        db,
        shop_id=shop_id,
        q=q,
        type_filter=type,
        sort=sort,
        page=page,
        page_size=page_size,
    )
