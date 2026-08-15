"""商家端权限 Catalog。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import TenantContext, get_tenant_context
from app.permissions import SHOP_MERCHANT_PERMISSIONS
from app.services.permission_service import require_any_permission

router = APIRouter(prefix="/permissions", tags=["shop-permissions"])


@router.get("/catalog")
def get_shop_permission_catalog(
    ctx: TenantContext = Depends(
        require_any_permission("shop.role.manage", "shop.analytics.read", "shop.product.read")
    ),
):
    """返回商家端 shop.* 权限码清单（任一商城读权限可访问）。"""
    _ = ctx
    return {
        "permissions": [
            {"code": code, "scope": "merchant"}
            for code in SHOP_MERCHANT_PERMISSIONS
        ]
    }


@router.get("/me")
def get_my_shop_permissions(ctx: TenantContext = Depends(get_tenant_context)):
    from app.services.membership_service import get_membership_permissions

    all_perms = get_membership_permissions(ctx.membership)
    shop_perms = sorted(p for p in all_perms if p.startswith("shop."))
    return {"permissions": shop_perms}
