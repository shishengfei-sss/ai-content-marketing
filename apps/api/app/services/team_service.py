"""企业角色与成员管理。"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import uuid_eq
from app.models import TenantMembership, TenantRole, TenantRolePermission, User
from app.permissions import ALL_PERMISSIONS, SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_EDITOR
from app.services.auth_service import hash_password, reset_user_password
from app.services.membership_service import get_membership, seed_tenant_roles


def _is_admin_role(role: TenantRole) -> bool:
    return role.is_system and role.code == SYSTEM_ROLE_ADMIN


def _assert_can_manage_target(operator: TenantMembership, target: TenantMembership | None, new_role: TenantRole | None = None) -> None:
    operator_is_admin = _is_admin_role(operator.role)
    if operator_is_admin:
        return
    if target and _is_admin_role(target.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="不能操作管理员成员")
    if new_role and _is_admin_role(new_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="不能设置管理员角色")


def _count_admins(db: Session, tenant_id: UUID) -> int:
    return (
        db.query(TenantMembership)
        .join(TenantRole, TenantMembership.role_id == TenantRole.id)
        .filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.is_active.is_(True),
            TenantRole.code == SYSTEM_ROLE_ADMIN,
        )
        .count()
    )


def list_roles(db: Session, tenant_id: UUID) -> list[TenantRole]:
    return (
        db.query(TenantRole)
        .options(joinedload(TenantRole.permissions))
        .filter(TenantRole.tenant_id == tenant_id)
        .order_by(TenantRole.is_system.desc(), TenantRole.created_at.asc())
        .all()
    )


def create_custom_role(db: Session, tenant_id: UUID, *, name: str, permissions: list[str]) -> TenantRole:
    invalid = set(permissions) - set(ALL_PERMISSIONS)
    if invalid:
        raise HTTPException(status_code=400, detail=f"无效权限: {', '.join(sorted(invalid))}")
    role = TenantRole(tenant_id=tenant_id, code=f"custom_{uuid4().hex[:8]}", name=name, is_system=False)
    db.add(role)
    db.flush()
    for code in permissions:
        db.add(TenantRolePermission(role_id=role.id, permission_code=code))
    db.commit()
    db.refresh(role)
    return role


def update_role_permissions(db: Session, tenant_id: UUID, role_id: UUID, *, name: str | None, permissions: list[str] | None) -> TenantRole:
    role = (
        db.query(TenantRole)
        .options(joinedload(TenantRole.permissions))
        .filter(uuid_eq(TenantRole.id, role_id), TenantRole.tenant_id == tenant_id)
        .first()
    )
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system and role.code == SYSTEM_ROLE_ADMIN:
        raise HTTPException(status_code=400, detail="不能修改管理员角色权限")
    if name is not None:
        role.name = name
    if permissions is not None:
        invalid = set(permissions) - set(ALL_PERMISSIONS)
        if invalid:
            raise HTTPException(status_code=400, detail=f"无效权限: {', '.join(sorted(invalid))}")
        role.permissions.clear()
        db.flush()
        for code in permissions:
            db.add(TenantRolePermission(role_id=role.id, permission_code=code))
    db.commit()
    db.refresh(role)
    return role


def delete_custom_role(db: Session, tenant_id: UUID, role_id: UUID) -> None:
    role = db.query(TenantRole).filter(uuid_eq(TenantRole.id, role_id), TenantRole.tenant_id == tenant_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="不能删除系统内置角色")
    member_count = db.query(TenantMembership).filter(TenantMembership.role_id == role.id).count()
    if member_count:
        raise HTTPException(status_code=400, detail="角色下仍有成员，无法删除")
    db.delete(role)
    db.commit()


def list_members(db: Session, tenant_id: UUID) -> list[TenantMembership]:
    return (
        db.query(TenantMembership)
        .options(
            joinedload(TenantMembership.user),
            joinedload(TenantMembership.role),
        )
        .filter(TenantMembership.tenant_id == tenant_id)
        .order_by(TenantMembership.joined_at.asc())
        .all()
    )


def add_member(
    db: Session,
    tenant_id: UUID,
    operator: TenantMembership,
    *,
    phone: str,
    display_name: str = "",
    password: str = "ChangeMe123",
) -> TenantMembership:
    editor_role = (
        db.query(TenantRole)
        .filter(TenantRole.tenant_id == tenant_id, TenantRole.code == SYSTEM_ROLE_EDITOR)
        .first()
    )
    if not editor_role:
        raise HTTPException(status_code=500, detail="企业角色未初始化")

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        user = User(
            phone=phone,
            hashed_password=hash_password(password),
            display_name=display_name or f"用户{phone[-4:]}",
            role="user",
            is_active=True,
        )
        db.add(user)
        db.flush()

    existing = get_membership(db, user.id, tenant_id)
    if existing:
        raise HTTPException(status_code=400, detail="该用户已是公司成员")

    _assert_can_manage_target(operator, None, editor_role)
    membership = TenantMembership(
        user_id=user.id,
        tenant_id=tenant_id,
        role_id=editor_role.id,
        is_active=True,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def update_member_role(
    db: Session,
    tenant_id: UUID,
    operator: TenantMembership,
    membership_id: UUID,
    role_id: UUID,
) -> TenantMembership:
    membership = (
        db.query(TenantMembership)
        .options(joinedload(TenantMembership.role), joinedload(TenantMembership.user))
        .filter(uuid_eq(TenantMembership.id, membership_id), TenantMembership.tenant_id == tenant_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="成员不存在")
    new_role = db.query(TenantRole).filter(uuid_eq(TenantRole.id, role_id), TenantRole.tenant_id == tenant_id).first()
    if not new_role:
        raise HTTPException(status_code=404, detail="角色不存在")

    _assert_can_manage_target(operator, membership, new_role)

    was_admin = _is_admin_role(membership.role)
    will_be_admin = _is_admin_role(new_role)
    if was_admin and not will_be_admin and _count_admins(db, tenant_id) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一名管理员")

    membership.role_id = new_role.id
    db.commit()
    db.refresh(membership)
    return membership


def disable_member(db: Session, tenant_id: UUID, operator: TenantMembership, membership_id: UUID) -> TenantMembership:
    membership = (
        db.query(TenantMembership)
        .options(joinedload(TenantMembership.role))
        .filter(uuid_eq(TenantMembership.id, membership_id), TenantMembership.tenant_id == tenant_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="成员不存在")
    _assert_can_manage_target(operator, membership)
    if _is_admin_role(membership.role) and _count_admins(db, tenant_id) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一名管理员")
    membership.is_active = False
    db.commit()
    db.refresh(membership)
    return membership
