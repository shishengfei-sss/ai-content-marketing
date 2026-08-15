"""平台端公域映射。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.shop_platform import ChannelMappingOut
from app.services.permission_service import require_platform_shop_permission
from app.services.shop import channel_service

router = APIRouter(prefix="/channel-mappings", tags=["platform-shop-channels"])


@router.post("/{mapping_id}/force-unmount", response_model=ChannelMappingOut)
def force_unmount(
    mapping_id: UUID,
    _user: User = Depends(require_platform_shop_permission("platform.shop.channel")),
    db: Session = Depends(get_db),
):
    return channel_service.force_unmount(db, mapping_id)


@router.get("/audit")
def platform_audit(
    external_order_id: str = Query(...),
    _user: User = Depends(require_platform_shop_permission("platform.shop.channel")),
    db: Session = Depends(get_db),
):
    items = channel_service.list_audit_by_external(db, external_order_id=external_order_id)
    return {"items": items, "total": len(items)}
