"""A16 角色 API。对照 #a16。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.services.permission_service import require_any_permission, require_permission
from app.services.shop import a16_roles_service as svc

router = APIRouter(prefix="/roles", tags=["shop-roles"])


@router.get("")
def list_roles(
    ctx: TenantContext = Depends(require_any_permission("shop.role.manage", "team.member.view")),
    db: Session = Depends(get_db),
):
    """内置角色列表（含 admin + shop_*、启用态、人数、权限矩阵只读）。"""
    return svc.list_a16_roles(db, ctx)


@router.post("/{role_code}/enable")
def enable_role(
    role_code: str,
    ctx: TenantContext = Depends(
        require_permission("shop.role.manage", forbidden_detail="无角色管理权限")
    ),
    db: Session = Depends(get_db),
):
    return svc.set_role_enabled(db, ctx, role_code, enabled=True)


@router.post("/{role_code}/disable")
def disable_role(
    role_code: str,
    ctx: TenantContext = Depends(
        require_permission("shop.role.manage", forbidden_detail="无角色管理权限")
    ),
    db: Session = Depends(get_db),
):
    return svc.set_role_enabled(db, ctx, role_code, enabled=False)
