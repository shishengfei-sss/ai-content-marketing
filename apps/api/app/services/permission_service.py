"""权限校验依赖。"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.dependencies import TenantContext, get_tenant_context


def require_permission(code: str) -> Callable:
    def _dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        perms = {p.permission_code for p in ctx.membership.role.permissions}
        if code not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
        return ctx

    return _dependency


def require_any_permission(*codes: str) -> Callable:
    def _dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        perms = {p.permission_code for p in ctx.membership.role.permissions}
        if not perms.intersection(codes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限")
        return ctx

    return _dependency
