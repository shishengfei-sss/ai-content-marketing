"""成员关系、企业角色与租户上下文。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import uuid_eq
from app.models import Tenant, TenantMembership, TenantRole, TenantRolePermission, User
from app.permissions import (
    ALL_PERMISSIONS,
    EDITOR_DEFAULT_PERMISSIONS,
    MARKETING_DEFAULT_PERMISSIONS,
    PLATFORM_ADMIN_ROLE,
    SALES_DEFAULT_PERMISSIONS,
    SALES_MANAGER_DEFAULT_PERMISSIONS,
    SYSTEM_ROLE_ADMIN,
    SYSTEM_ROLE_EDITOR,
    SYSTEM_ROLE_MARKETING,
    SYSTEM_ROLE_SALES,
    SYSTEM_ROLE_SALES_MANAGER,
)


def _add_role_permissions(db: Session, role_id: UUID, codes: frozenset[str] | set[str]) -> None:
    for code in codes:
        db.add(TenantRolePermission(role_id=role_id, permission_code=code))


def seed_tenant_roles(db: Session, tenant_id: UUID) -> tuple[TenantRole, TenantRole]:
    admin = TenantRole(
        tenant_id=tenant_id,
        code=SYSTEM_ROLE_ADMIN,
        name="企业管理员",
        is_system=True,
    )
    editor = TenantRole(
        tenant_id=tenant_id,
        code=SYSTEM_ROLE_EDITOR,
        name="编辑",
        is_system=True,
    )
    sales = TenantRole(
        tenant_id=tenant_id,
        code=SYSTEM_ROLE_SALES,
        name="销售",
        is_system=True,
    )
    sales_manager = TenantRole(
        tenant_id=tenant_id,
        code=SYSTEM_ROLE_SALES_MANAGER,
        name="销售经理",
        is_system=True,
    )
    marketing = TenantRole(
        tenant_id=tenant_id,
        code=SYSTEM_ROLE_MARKETING,
        name="市场运营",
        is_system=True,
    )
    for role in (admin, editor, sales, sales_manager, marketing):
        db.add(role)
    db.flush()

    _add_role_permissions(db, admin.id, ALL_PERMISSIONS)
    _add_role_permissions(db, editor.id, EDITOR_DEFAULT_PERMISSIONS)
    _add_role_permissions(db, sales.id, SALES_DEFAULT_PERMISSIONS)
    _add_role_permissions(db, sales_manager.id, SALES_MANAGER_DEFAULT_PERMISSIONS)
    _add_role_permissions(db, marketing.id, MARKETING_DEFAULT_PERMISSIONS)
    db.flush()
    return admin, editor


def create_tenant_with_admin(
    db: Session,
    *,
    name: str,
    industry_code: str,
    user: User,
) -> TenantMembership:
    tenant = Tenant(name=name, industry_code=industry_code)
    db.add(tenant)
    db.flush()
    admin_role, _editor = seed_tenant_roles(db, tenant.id)
    membership = TenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        role_id=admin_role.id,
        is_active=True,
    )
    db.add(membership)
    user.tenant_id = tenant.id
    db.flush()
    return membership


def list_active_memberships(db: Session, user_id: UUID) -> list[TenantMembership]:
    memberships = (
        db.query(TenantMembership)
        .options(
            joinedload(TenantMembership.tenant),
            joinedload(TenantMembership.role).joinedload(TenantRole.permissions),
        )
        .filter(
            TenantMembership.user_id == user_id,
            TenantMembership.is_active.is_(True),
        )
        .order_by(TenantMembership.joined_at.asc())
        .all()
    )
    for m in memberships:
        if m.role is None:
            role = (
                db.query(TenantRole)
                .options(joinedload(TenantRole.permissions))
                .filter(uuid_eq(TenantRole.id, m.role_id))
                .first()
            )
            if role:
                m.role = role
    return memberships


def get_membership(db: Session, user_id: UUID, tenant_id: UUID) -> TenantMembership | None:
    membership = (
        db.query(TenantMembership)
        .options(
            joinedload(TenantMembership.tenant),
            joinedload(TenantMembership.role).joinedload(TenantRole.permissions),
        )
        .filter(
            TenantMembership.user_id == user_id,
            uuid_eq(TenantMembership.tenant_id, tenant_id),
            TenantMembership.is_active.is_(True),
        )
        .first()
    )
    if membership and membership.role is None:
        role = (
            db.query(TenantRole)
            .options(joinedload(TenantRole.permissions))
            .filter(uuid_eq(TenantRole.id, membership.role_id))
            .first()
        )
        if role:
            membership.role = role
    return membership


def get_membership_permissions(membership: TenantMembership) -> list[str]:
    return sorted({p.permission_code for p in membership.role.permissions})


def is_platform_admin(user: User) -> bool:
    return user.role == PLATFORM_ADMIN_ROLE


def pick_default_tenant_id(db: Session, user: User) -> UUID | None:
    if is_platform_admin(user):
        return user.tenant_id
    memberships = list_active_memberships(db, user.id)
    if len(memberships) == 1:
        return memberships[0].tenant_id
    return None


def assert_membership_access(db: Session, user: User, tenant_id: UUID) -> TenantMembership:
    if is_platform_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="平台管理员请使用用户工作台")
    membership = get_membership(db, user.id, tenant_id)
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该公司")
    return membership
