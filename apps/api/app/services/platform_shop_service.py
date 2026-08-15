"""平台商城运营权限（platform.shop.*，跨租户）。"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import ShopPlatformPermissionAudit, User
from app.permissions import (
    PLATFORM_ADMIN_ROLE,
    PLATFORM_SHOP_PERMISSION_LABELS,
    PLATFORM_SHOP_PERMISSIONS,
    PLATFORM_SHOP_ROLE_CODES,
    PLATFORM_SHOP_ROLE_CS,
    PLATFORM_SHOP_ROLE_DEFAULT_PERMISSIONS,
    PLATFORM_SHOP_ROLE_MATRIX_CODES,
    PLATFORM_SHOP_ROLE_META,
)

PERMISSION_AUDIT_ACTION_LABELS: dict[str, str] = {
    "bind_role": "绑定角色",
    "tune_permissions": "微调权限",
    "clear_role": "清空商城角色",
}


def shop_role_display_name(code: str | None) -> str:
    if not code:
        return "平台超管"
    for meta in PLATFORM_SHOP_ROLE_META:
        if meta.get("code") == code:
            return meta.get("name") or code
    return code


def _perm_label(code: str) -> str:
    return PLATFORM_SHOP_PERMISSION_LABELS.get(code, code)


def record_shop_permission_audit(
    db: Session,
    *,
    target_user_id,
    operator_user_id,
    role_from: str | None,
    role_to: str | None,
    permissions_from: list[str],
    permissions_to: list[str],
) -> ShopPlatformPermissionAudit | None:
    """保存商城角色/权限后写一行审计。无变更则跳过。对照 #p08b。"""
    from_role = role_from or None
    to_role = role_to or None
    from_set = set(permissions_from or [])
    to_set = set(permissions_to or [])
    if from_role == to_role and from_set == to_set:
        return None
    if from_role != to_role and not to_role:
        action = "clear_role"
    elif from_role != to_role:
        action = "bind_role"
    else:
        action = "tune_permissions"
    parts: list[str] = []
    if from_role != to_role:
        parts.append(f"角色：{shop_role_display_name(from_role)} → {shop_role_display_name(to_role)}")
    removed = sorted(from_set - to_set)
    added = sorted(to_set - from_set)
    if removed:
        parts.append("收回 " + "、".join(_perm_label(c) for c in removed))
    if added:
        parts.append("授予 " + "、".join(_perm_label(c) for c in added))
    summary = "；".join(parts) or PERMISSION_AUDIT_ACTION_LABELS[action]
    row = ShopPlatformPermissionAudit(
        target_user_id=target_user_id,
        operator_user_id=operator_user_id,
        action=action,
        role_from=from_role,
        role_to=to_role,
        permissions_from=sorted(from_set),
        permissions_to=sorted(to_set),
        summary=summary,
    )
    db.add(row)
    return row


def list_shop_permission_audits(
    db: Session,
    target_user_id,
    *,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    from app.database import uuid_eq

    q = (
        db.query(ShopPlatformPermissionAudit)
        .filter(uuid_eq(ShopPlatformPermissionAudit.target_user_id, target_user_id))
        .order_by(ShopPlatformPermissionAudit.created_at.desc())
    )
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    names: dict[str, str] = {}
    for row in rows:
        key = str(row.operator_user_id)
        if key in names:
            continue
        op = db.query(User).filter(uuid_eq(User.id, row.operator_user_id)).first()
        names[key] = (op.display_name or op.phone or "—") if op else "—"
    items = [
        {
            "id": row.id,
            "target_user_id": row.target_user_id,
            "operator_user_id": row.operator_user_id,
            "operator_name": names.get(str(row.operator_user_id), "—"),
            "action": row.action,
            "action_label": PERMISSION_AUDIT_ACTION_LABELS.get(row.action, row.action),
            "summary": row.summary,
            "created_at": row.created_at,
        }
        for row in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_platform_shop_role(user: User) -> str | None:
    if user.role != PLATFORM_ADMIN_ROLE:
        return None
    raw = getattr(user, "platform_shop_role", None)
    if raw and raw in PLATFORM_SHOP_ROLE_CODES:
        return raw
    return None


def is_platform_shop_superadmin(user: User) -> bool:
    return user.role == PLATFORM_ADMIN_ROLE and get_platform_shop_role(user) is None


def get_platform_shop_permissions(user: User) -> list[str]:
    """平台账号的商城权限列表。未设子角色模板时默认全部 platform.shop.*。"""
    if user.role != PLATFORM_ADMIN_ROLE:
        return []
    template = get_platform_shop_role(user)
    if template is None:
        return sorted(PLATFORM_SHOP_PERMISSIONS)
    perms = PLATFORM_SHOP_ROLE_DEFAULT_PERMISSIONS.get(template)
    if perms is None:
        return sorted(PLATFORM_SHOP_PERMISSIONS)
    override = getattr(user, "platform_shop_permissions", None)
    if isinstance(override, list) and override:
        return sorted(set(override).intersection(perms))
    if isinstance(override, list) and len(override) == 0:
        return []
    return sorted(perms)


def user_has_platform_shop_permission(user: User, code: str) -> bool:
    return code in set(get_platform_shop_permissions(user))


def assert_can_initiate_onboarding(user: User) -> None:
    """发起入驻（P02-A）仅商家管家或平台超管（未绑子角色模板）可操作。"""
    if not user_has_platform_shop_permission(user, "platform.shop.onboarding.initiate"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无发起入驻权限")
    template = get_platform_shop_role(user)
    if template is None:
        return
    if template != PLATFORM_SHOP_ROLE_CS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅商家管家可发起入驻")


def assert_can_manage_shop_accounts(user: User) -> None:
    """P08-B / 主站账号：仅平台超管可改角色与商城权限。对照 #p08-admin-users。"""
    if not is_platform_shop_superadmin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无账号管理权限")


def apply_shop_permission_override(user: User, codes: list[str] | None) -> None:
    template = get_platform_shop_role(user)
    if template is None:
        user.platform_shop_permissions = None
        return
    allowed = PLATFORM_SHOP_ROLE_DEFAULT_PERMISSIONS[template]
    if codes is None:
        user.platform_shop_permissions = None
        return
    extra = set(codes) - allowed
    if extra:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="不可授予超出角色默认的权限",
        )
    chosen = set(codes).intersection(allowed)
    if chosen == allowed:
        user.platform_shop_permissions = None
    else:
        user.platform_shop_permissions = sorted(chosen)


def _matrix_for(role_code: str) -> list[dict]:
    defaults = PLATFORM_SHOP_ROLE_DEFAULT_PERMISSIONS.get(role_code, frozenset())
    codes = PLATFORM_SHOP_ROLE_MATRIX_CODES.get(role_code) or tuple(sorted(defaults))
    rows = []
    for code in codes:
        rows.append(
            {
                "code": code,
                "label": PLATFORM_SHOP_PERMISSION_LABELS.get(code, code),
                "granted": code in defaults,
            }
        )
    return rows


def build_permission_catalog(db: Session) -> dict:
    """P08 Catalog + 内置角色绑定人数。对照 #p08a · TC-P08-F01。"""
    admins = (
        db.query(User.platform_shop_role)
        .filter(User.role == PLATFORM_ADMIN_ROLE, User.is_active.is_(True))
        .all()
    )
    bound: dict[str, int] = {"": 0}
    for code in PLATFORM_SHOP_ROLE_CODES:
        bound[code] = 0
    for (raw,) in admins:
        key = raw if raw in PLATFORM_SHOP_ROLE_CODES else ""
        bound[key] = bound.get(key, 0) + 1

    roles = []
    for meta in PLATFORM_SHOP_ROLE_META:
        code = meta["code"]
        if code:
            defaults = sorted(PLATFORM_SHOP_ROLE_DEFAULT_PERMISSIONS.get(code, frozenset()))
            matrix = _matrix_for(code)
        else:
            defaults = sorted(PLATFORM_SHOP_PERMISSIONS)
            matrix = [
                {
                    "code": c,
                    "label": PLATFORM_SHOP_PERMISSION_LABELS.get(c, c),
                    "granted": True,
                }
                for c in PLATFORM_SHOP_PERMISSIONS
            ]
        roles.append(
            {
                **meta,
                "enabled": True,
                "bound_count": bound.get(code, 0),
                "default_permissions": defaults,
                "matrix": matrix,
            }
        )

    return {
        "permissions": [
            {
                "code": code,
                "scope": "platform",
                "label": PLATFORM_SHOP_PERMISSION_LABELS.get(code, code),
            }
            for code in PLATFORM_SHOP_PERMISSIONS
        ],
        "role_templates": sorted(PLATFORM_SHOP_ROLE_CODES),
        "roles": roles,
    }
