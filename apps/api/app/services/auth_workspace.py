"""登录工作区：平台运营 vs 商家企业（同账号不同入口）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import TenantMembership, User
from app.services.membership_service import get_membership, is_platform_admin, list_active_memberships

WORKSPACE_PLATFORM = "platform"
WORKSPACE_MERCHANT = "merchant"
VALID_WORKSPACES = frozenset({WORKSPACE_PLATFORM, WORKSPACE_MERCHANT})


def resolve_workspace_mode(
    user: User,
    memberships: list[TenantMembership],
    requested: str | None,
) -> str:
    if requested in VALID_WORKSPACES:
        return requested
    if is_platform_admin(user) and not memberships:
        return WORKSPACE_PLATFORM
    return WORKSPACE_MERCHANT


def workspace_mode_from_payload_with_db(
    db: Session,
    payload: dict,
    user: User,
) -> str:
    raw = payload.get("workspace_mode")
    if raw in VALID_WORKSPACES:
        return raw
    memberships = list_active_memberships(db, user.id)
    if is_platform_admin(user):
        raw_tid = payload.get("active_tenant_id")
        if raw_tid:
            try:
                tid = UUID(str(raw_tid))
                if get_membership(db, user.id, tid):
                    return WORKSPACE_MERCHANT
            except ValueError:
                pass
        if not memberships:
            return WORKSPACE_PLATFORM
        return WORKSPACE_MERCHANT
    return WORKSPACE_MERCHANT


def validate_workspace_login(
    user: User,
    memberships: list[TenantMembership],
    workspace_mode: str,
) -> None:
    if workspace_mode == WORKSPACE_PLATFORM:
        if not is_platform_admin(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="请使用商家登录入口 /login",
            )
        return
    if not memberships:
        if is_platform_admin(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="该账号无企业成员关系，请使用平台运营登录 /admin/login",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您尚未加入任何企业",
        )


def pick_merchant_tenant_id(db: Session, user: User) -> UUID | None:
    memberships = list_active_memberships(db, user.id)
    if len(memberships) == 1:
        return memberships[0].tenant_id
    if user.tenant_id and get_membership(db, user.id, user.tenant_id):
        return user.tenant_id
    return None


def build_token_extra(
    db: Session,
    user: User,
    workspace_mode: str,
) -> tuple[dict, bool]:
    memberships = list_active_memberships(db, user.id)
    extra: dict = {"role": user.role, "workspace_mode": workspace_mode}
    need_select = False
    if workspace_mode == WORKSPACE_MERCHANT:
        active_tenant_id = pick_merchant_tenant_id(db, user)
        need_select = len(memberships) > 1 and not active_tenant_id
        if active_tenant_id:
            extra["active_tenant_id"] = str(active_tenant_id)
    return extra, need_select
