"""A16 角色与成员。对照 PRD 01#a16 · #a16a · §8.7.1。"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import TenantMembership, TenantRole
from app.models.shop import ShopStore, ShopStoreMembership
from app.permissions import (
    SHOP_BUILTIN_ROLE_CODES,
    SHOP_BUILTIN_ROLE_DEFAULT_PERMISSIONS,
    SYSTEM_ROLE_ADMIN,
    SYSTEM_ROLE_EDITOR,
)
from app.services.membership_service import seed_tenant_roles
from app.services.shop.a15_sms_settings_service import _ensure_settings

A16_ROLE_ORDER = (
    SYSTEM_ROLE_ADMIN,
    "shop_admin",
    "shop_content",
    "shop_support",
    "shop_clerk",
)

ROLE_LABELS = {
    SYSTEM_ROLE_ADMIN: "企业管理员",
    "shop_admin": "店铺管理员",
    "shop_content": "内容运营",
    "shop_support": "客服",
    "shop_clerk": "店员",
}


def _mask_phone(phone: str | None) -> str:
    if not phone or len(phone) < 7:
        return phone or "—"
    return f"{phone[:3]}****{phone[-4:]}"


def _disabled_codes(db: Session, tenant_id: UUID) -> set[str]:
    row = _ensure_settings(db, tenant_id)
    raw = row.disabled_shop_role_codes or []
    return {str(c) for c in raw}


def _set_disabled(db: Session, tenant_id: UUID, codes: set[str]) -> None:
    row = _ensure_settings(db, tenant_id)
    row.disabled_shop_role_codes = sorted(codes)
    db.commit()


def _ensure_shop_roles(db: Session, tenant_id: UUID) -> None:
    from app.models import TenantRolePermission

    existing = {
        r.code: r
        for r in db.query(TenantRole).filter(uuid_eq(TenantRole.tenant_id, tenant_id)).all()
    }
    changed = False
    for code in SHOP_BUILTIN_ROLE_CODES:
        if code in existing:
            continue
        role = TenantRole(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            code=code,
            name=ROLE_LABELS.get(code, code),
            is_system=True,
        )
        db.add(role)
        db.flush()
        for p in sorted(SHOP_BUILTIN_ROLE_DEFAULT_PERMISSIONS.get(code, frozenset())):
            db.add(TenantRolePermission(id=uuid.uuid4(), role_id=role.id, permission_code=p))
        changed = True
    if SYSTEM_ROLE_EDITOR not in existing:
        editor = TenantRole(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            code=SYSTEM_ROLE_EDITOR,
            name="编辑",
            is_system=True,
        )
        db.add(editor)
        changed = True
    if changed:
        db.commit()


def _role_by_code(db: Session, tenant_id: UUID, code: str) -> TenantRole | None:
    return (
        db.query(TenantRole)
        .options(joinedload(TenantRole.permissions))
        .filter(uuid_eq(TenantRole.tenant_id, tenant_id), TenantRole.code == code)
        .first()
    )


def _member_count(db: Session, tenant_id: UUID, role_id: UUID) -> int:
    return (
        db.query(TenantMembership)
        .filter(
            uuid_eq(TenantMembership.tenant_id, tenant_id),
            uuid_eq(TenantMembership.role_id, role_id),
            TenantMembership.is_active.is_(True),
        )
        .count()
    )


def list_a16_roles(db: Session, ctx: TenantContext) -> list[dict[str, Any]]:
    _ensure_shop_roles(db, ctx.tenant_id)
    disabled = _disabled_codes(db, ctx.tenant_id)
    out: list[dict[str, Any]] = []
    for code in A16_ROLE_ORDER:
        role = _role_by_code(db, ctx.tenant_id, code)
        if not role:
            continue
        enabled = code == SYSTEM_ROLE_ADMIN or code not in disabled
        perms = sorted({p.permission_code for p in role.permissions})
        if code == SYSTEM_ROLE_ADMIN and not perms:
            # admin 通常隐式全权限；展示用 shop.* 摘要
            perms = ["*"]
        out.append(
            {
                "id": str(role.id),
                "code": role.code,
                "name": role.name or ROLE_LABELS.get(code, code),
                "is_system": bool(role.is_system) or code == SYSTEM_ROLE_ADMIN,
                "enabled": enabled,
                "member_count": _member_count(db, ctx.tenant_id, role.id),
                "permissions": perms,
                "can_disable": code != SYSTEM_ROLE_ADMIN,
                "can_assign": enabled,
            }
        )
    return out


def set_role_enabled(db: Session, ctx: TenantContext, role_code: str, *, enabled: bool) -> dict[str, Any]:
    if role_code == SYSTEM_ROLE_ADMIN:
        raise HTTPException(status_code=422, detail="系统角色不可操作")
    if role_code not in SHOP_BUILTIN_ROLE_CODES:
        raise HTTPException(status_code=404, detail="角色不存在")
    _ensure_shop_roles(db, ctx.tenant_id)
    role = _role_by_code(db, ctx.tenant_id, role_code)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    disabled = _disabled_codes(db, ctx.tenant_id)
    if enabled:
        if role_code not in disabled:
            # already enabled
            return next(r for r in list_a16_roles(db, ctx) if r["code"] == role_code)
        disabled.discard(role_code)
        _set_disabled(db, ctx.tenant_id, disabled)
    else:
        if role_code in disabled:
            return next(r for r in list_a16_roles(db, ctx) if r["code"] == role_code)
        cnt = _member_count(db, ctx.tenant_id, role.id)
        if cnt > 0:
            raise HTTPException(status_code=422, detail="仍有成员绑定，请先换绑")
        disabled.add(role_code)
        _set_disabled(db, ctx.tenant_id, disabled)
    return next(r for r in list_a16_roles(db, ctx) if r["code"] == role_code)


def _store_scope_for_user(db: Session, tenant_id: UUID, user_id: UUID, role_code: str) -> dict[str, Any]:
    if role_code in (SYSTEM_ROLE_ADMIN, "shop_admin", "shop_content", "shop_support"):
        return {"store_scope": "all", "store_ids": [], "store_names": ["全部店铺"]}
    rows = (
        db.query(ShopStoreMembership, ShopStore)
        .join(ShopStore, ShopStore.id == ShopStoreMembership.shop_id)
        .filter(
            uuid_eq(ShopStoreMembership.tenant_id, tenant_id),
            uuid_eq(ShopStoreMembership.user_id, user_id),
        )
        .all()
    )
    if not rows:
        return {"store_scope": "selected", "store_ids": [], "store_names": []}
    return {
        "store_scope": "selected",
        "store_ids": [str(s.id) for _, s in rows],
        "store_names": [s.name for _, s in rows],
    }


def list_shop_members(db: Session, ctx: TenantContext, *, role_code: str | None = None) -> list[dict[str, Any]]:
    _ensure_shop_roles(db, ctx.tenant_id)
    q = (
        db.query(TenantMembership)
        .options(joinedload(TenantMembership.user), joinedload(TenantMembership.role))
        .filter(uuid_eq(TenantMembership.tenant_id, ctx.tenant_id), TenantMembership.is_active.is_(True))
    )
    items = []
    for m in q.all():
        code = m.role.code if m.role else ""
        if code not in A16_ROLE_ORDER:
            continue
        if role_code and code != role_code:
            continue
        scope = _store_scope_for_user(db, ctx.tenant_id, m.user_id, code)
        u = m.user
        items.append(
            {
                "user_id": str(m.user_id),
                "membership_id": str(m.id),
                "display_name": (u.display_name if u else None) or "—",
                "phone": u.phone if u else None,
                "phone_masked": _mask_phone(u.phone if u else None),
                "email": getattr(u, "email", None) if u else None,
                "role_code": code,
                "role_name": (m.role.name if m.role else None) or ROLE_LABELS.get(code, code),
                "role_id": str(m.role_id),
                **scope,
            }
        )
    return items


def list_assignable_users(db: Session, ctx: TenantContext) -> list[dict[str, Any]]:
    """企业成员（可分配商城角色）。"""
    rows = (
        db.query(TenantMembership)
        .options(joinedload(TenantMembership.user), joinedload(TenantMembership.role))
        .filter(uuid_eq(TenantMembership.tenant_id, ctx.tenant_id), TenantMembership.is_active.is_(True))
        .all()
    )
    out = []
    for m in rows:
        u = m.user
        if not u:
            continue
        out.append(
            {
                "user_id": str(m.user_id),
                "display_name": u.display_name or "—",
                "phone_masked": _mask_phone(u.phone),
                "current_role_code": m.role.code if m.role else None,
                "current_role_name": m.role.name if m.role else None,
            }
        )
    return out


def _clear_store_memberships(db: Session, tenant_id: UUID, user_id: UUID) -> None:
    db.query(ShopStoreMembership).filter(
        uuid_eq(ShopStoreMembership.tenant_id, tenant_id),
        uuid_eq(ShopStoreMembership.user_id, user_id),
    ).delete(synchronize_session=False)


def _set_store_memberships(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    role_id: UUID,
    store_ids: list[UUID],
) -> None:
    _clear_store_memberships(db, tenant_id, user_id)
    for sid in store_ids:
        shop = (
            db.query(ShopStore)
            .filter(uuid_eq(ShopStore.id, sid), uuid_eq(ShopStore.tenant_id, tenant_id))
            .first()
        )
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
        db.add(
            ShopStoreMembership(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                shop_id=sid,
                role_id=role_id,
            )
        )


def assign_member(
    db: Session,
    ctx: TenantContext,
    *,
    user_id: UUID,
    role_code: str,
    store_scope: str = "all",
    store_ids: list[UUID] | None = None,
) -> dict[str, Any]:
    _ensure_shop_roles(db, ctx.tenant_id)
    if role_code not in A16_ROLE_ORDER:
        raise HTTPException(status_code=422, detail="仅可绑定内置角色")
    if role_code != SYSTEM_ROLE_ADMIN and role_code in _disabled_codes(db, ctx.tenant_id):
        raise HTTPException(status_code=422, detail="角色已禁用")

    role = _role_by_code(db, ctx.tenant_id, role_code)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    mem = (
        db.query(TenantMembership)
        .options(joinedload(TenantMembership.role))
        .filter(
            uuid_eq(TenantMembership.tenant_id, ctx.tenant_id),
            uuid_eq(TenantMembership.user_id, user_id),
            TenantMembership.is_active.is_(True),
        )
        .first()
    )
    if not mem:
        raise HTTPException(status_code=422, detail="成员须为企业成员")

    if mem.role and mem.role.code == role_code:
        # 已是该角色：允许更新店铺范围
        pass
    elif mem.role and mem.role.code in A16_ROLE_ORDER and mem.role.code != role_code:
        # 换绑允许
        pass

    ids = list(store_ids or [])
    scope = store_scope or "all"
    if role_code == "shop_clerk":
        if scope != "selected" or len(ids) != 1:
            raise HTTPException(status_code=422, detail="店员仅能绑定一个店铺")
    elif role_code == SYSTEM_ROLE_ADMIN:
        scope = "all"
        ids = []
    else:
        if scope == "selected" and not ids:
            raise HTTPException(status_code=422, detail="请选择店铺范围")
        if scope == "all":
            ids = []

    mem.role_id = role.id
    if role_code == "shop_clerk" or (scope == "selected" and ids):
        _set_store_memberships(
            db, tenant_id=ctx.tenant_id, user_id=user_id, role_id=role.id, store_ids=ids
        )
    else:
        _clear_store_memberships(db, ctx.tenant_id, user_id)
    db.commit()

    members = list_shop_members(db, ctx)
    hit = next((m for m in members if m["user_id"] == str(user_id)), None)
    if not hit:
        raise HTTPException(status_code=500, detail="分配后读取失败")
    return hit


def update_member(
    db: Session,
    ctx: TenantContext,
    user_id: UUID,
    *,
    role_code: str | None = None,
    store_scope: str | None = None,
    store_ids: list[UUID] | None = None,
) -> dict[str, Any]:
    mem = (
        db.query(TenantMembership)
        .options(joinedload(TenantMembership.role))
        .filter(
            uuid_eq(TenantMembership.tenant_id, ctx.tenant_id),
            uuid_eq(TenantMembership.user_id, user_id),
            TenantMembership.is_active.is_(True),
        )
        .first()
    )
    if not mem or not mem.role or mem.role.code not in A16_ROLE_ORDER:
        raise HTTPException(status_code=404, detail="商城成员不存在")
    code = role_code or mem.role.code
    scope = store_scope
    if scope is None:
        existing = _store_scope_for_user(db, ctx.tenant_id, user_id, mem.role.code)
        scope = existing["store_scope"]
        if store_ids is None and existing["store_ids"]:
            store_ids = [UUID(x) for x in existing["store_ids"]]
    return assign_member(
        db,
        ctx,
        user_id=user_id,
        role_code=code,
        store_scope=scope or "all",
        store_ids=store_ids,
    )


def remove_member(db: Session, ctx: TenantContext, user_id: UUID) -> dict[str, Any]:
    """移除商城角色：回落到 editor（不删 user）。"""
    mem = (
        db.query(TenantMembership)
        .options(joinedload(TenantMembership.role))
        .filter(
            uuid_eq(TenantMembership.tenant_id, ctx.tenant_id),
            uuid_eq(TenantMembership.user_id, user_id),
            TenantMembership.is_active.is_(True),
        )
        .first()
    )
    if not mem or not mem.role or mem.role.code not in A16_ROLE_ORDER:
        raise HTTPException(status_code=404, detail="商城成员不存在")
    if mem.role.code == SYSTEM_ROLE_ADMIN:
        # 不允许通过 A16 移除最后一个企业管理员
        admins = _member_count(db, ctx.tenant_id, mem.role_id)
        if admins <= 1:
            raise HTTPException(status_code=422, detail="至少保留一名企业管理员")
    editor = _role_by_code(db, ctx.tenant_id, SYSTEM_ROLE_EDITOR)
    if not editor:
        seed_tenant_roles(db, ctx.tenant_id)
        editor = _role_by_code(db, ctx.tenant_id, SYSTEM_ROLE_EDITOR)
    if not editor:
        raise HTTPException(status_code=500, detail="缺少编辑角色")
    mem.role_id = editor.id
    _clear_store_memberships(db, ctx.tenant_id, user_id)
    db.commit()
    return {"ok": True, "user_id": str(user_id), "role_code": SYSTEM_ROLE_EDITOR}
