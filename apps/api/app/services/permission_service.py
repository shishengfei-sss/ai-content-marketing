"""权限校验依赖。"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.dependencies import TenantContext, get_tenant_context, require_platform_admin
from app.models import User


def require_permission(code: str, *, forbidden_detail: str = "无权限") -> Callable:
    def _dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        from sqlalchemy.orm import object_session

        from app.services.membership_service import get_membership_permissions

        perms = set(get_membership_permissions(ctx.membership, object_session(ctx.membership)))
        if code not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=forbidden_detail)
        return ctx

    return _dependency


def require_any_permission(*codes: str) -> Callable:
    def _dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        from sqlalchemy.orm import object_session

        from app.services.membership_service import get_membership_permissions

        perms = set(get_membership_permissions(ctx.membership, object_session(ctx.membership)))
        if not perms.intersection(codes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
        return ctx

    return _dependency


def require_platform_shop_permission(code: str) -> Callable:
    """平台运营端商城 API：校验 platform.shop.*（须 platform_admin 账号）。"""

    def _dependency(user: User = Depends(require_platform_admin)) -> User:
        from app.services.platform_shop_service import user_has_platform_shop_permission

        if not user_has_platform_shop_permission(user, code):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
        return user

    return _dependency


def require_platform_shop_any(*codes: str) -> Callable:
    def _dependency(user: User = Depends(require_platform_admin)) -> User:
        from app.services.platform_shop_service import get_platform_shop_permissions

        perms = set(get_platform_shop_permissions(user))
        if not perms.intersection(codes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
        return user

    return _dependency
