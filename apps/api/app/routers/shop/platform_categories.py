"""商家端只读平台类目（A03 下拉）。对照 PRD #a03 · GET /shop/platform-categories。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import PlatformCategoryListResponse
from app.services.permission_service import require_permission
from app.services.shop import category_service

router = APIRouter(prefix="/platform-categories", tags=["shop-platform-categories"])


@router.get("", response_model=PlatformCategoryListResponse)
def list_platform_categories(
    status: str | None = Query(default="enabled"),
    ctx: TenantContext = Depends(require_permission("shop.product.read")),
    db: Session = Depends(get_db),
):
    items = category_service.list_for_merchant(db, status=status or "enabled")
    return PlatformCategoryListResponse(
        items=items, total=len(items), page=1, page_size=len(items) or 20
    )
