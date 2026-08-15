"""平台商城权限 Catalog 与当前账号权限。对照 06#p08a。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.permission_service import require_platform_admin
from app.services.platform_shop_service import (
    build_permission_catalog,
    get_platform_shop_permissions,
    get_platform_shop_role,
)

router = APIRouter(prefix="/permissions", tags=["platform-shop-permissions"])


@router.get("/catalog")
def get_platform_shop_permission_catalog(
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    return build_permission_catalog(db)


@router.get("/me")
def get_my_platform_shop_permissions(user: User = Depends(require_platform_admin)):
    return {
        "platform_shop_role": get_platform_shop_role(user),
        "permissions": get_platform_shop_permissions(user),
    }
