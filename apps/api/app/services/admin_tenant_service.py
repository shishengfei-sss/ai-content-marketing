"""平台后台：企业管理与管理员转移。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import uuid_eq
from app.models import Tenant, TenantMembership, TenantRole, User
from app.permissions import SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_EDITOR
from app.services.membership_service import get_membership
from app.services.platform_llm_service import get_quota_status


def _tenant_to_dict(db: Session, tenant: Tenant) -> dict:
    member_count = (
        db.query(func.count(TenantMembership.id))
        .filter(
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.is_active.is_(True),
        )
        .scalar()
        or 0
    )
    admin_rows = (
        db.query(TenantMembership)
        .options(joinedload(TenantMembership.user))
        .join(TenantRole, TenantMembership.role_id == TenantRole.id)
        .filter(
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.is_active.is_(True),
            TenantRole.code == SYSTEM_ROLE_ADMIN,
        )
        .all()
    )
    quota = get_quota_status(db, tenant.id)
    return {
        "id": tenant.id,
        "name": tenant.name,
        "credit_code": tenant.credit_code,
        "industry_code": tenant.industry_code,
        "member_count": member_count,
        "admin_summaries": [
            {
                "user_id": row.user_id,
                "phone": row.user.phone,
                "display_name": row.user.display_name,
            }
            for row in admin_rows
        ],
        "quota_used": quota["used_count"],
        "quota_limit": quota["quota_limit"],
        "created_at": tenant.created_at,
    }


def list_tenants_admin(
    db: Session,
    *,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    query = db.query(Tenant)
    if q:
        like = f"%{q.strip()}%"
        query = (
            query.outerjoin(TenantMembership, TenantMembership.tenant_id == Tenant.id)
            .outerjoin(User, User.id == TenantMembership.user_id)
            .outerjoin(TenantRole, TenantRole.id == TenantMembership.role_id)
            .filter(
                or_(
                    Tenant.name.ilike(like),
                    Tenant.credit_code.ilike(like),
                    User.phone.ilike(like),
                )
            )
            .distinct()
        )

    total = query.count()
    tenants = (
        query.order_by(Tenant.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: list[dict] = []
    for tenant in tenants:
        items.append(_tenant_to_dict(db, tenant))
    return items, total


def get_tenant_admin(db: Session, tenant_id: UUID) -> dict | None:
    tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, tenant_id)).first()
    if not tenant:
        return None
    return _tenant_to_dict(db, tenant)


def list_tenant_members_admin(db: Session, tenant_id: UUID) -> list[dict]:
    rows = (
        db.query(TenantMembership)
        .options(
            joinedload(TenantMembership.user),
            joinedload(TenantMembership.role),
        )
        .filter(TenantMembership.tenant_id == tenant_id)
        .order_by(TenantMembership.joined_at.asc())
        .all()
    )
    return [
        {
            "membership_id": row.id,
            "user_id": row.user_id,
            "phone": row.user.phone,
            "display_name": row.user.display_name,
            "role_code": row.role.code,
            "role_name": row.role.name,
            "membership_active": row.is_active,
            "user_active": row.user.is_active,
            "joined_at": row.joined_at,
        }
        for row in rows
    ]


def transfer_tenant_admin(
    db: Session,
    tenant_id: UUID,
    new_admin_user_id: UUID,
    *,
    actor_id: UUID,
) -> None:
    _ = actor_id
    tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, tenant_id)).first()
    if not tenant:
        raise ValueError("TENANT_NOT_FOUND")

    target = get_membership(db, new_admin_user_id, tenant_id)
    if not target:
        raise ValueError("MEMBER_NOT_FOUND")
    if target.role.code == SYSTEM_ROLE_ADMIN:
        raise ValueError("ALREADY_ADMIN")
    if not target.user.is_active:
        raise ValueError("USER_INACTIVE")

    admin_role = (
        db.query(TenantRole)
        .filter(TenantRole.tenant_id == tenant_id, TenantRole.code == SYSTEM_ROLE_ADMIN)
        .first()
    )
    editor_role = (
        db.query(TenantRole)
        .filter(TenantRole.tenant_id == tenant_id, TenantRole.code == SYSTEM_ROLE_EDITOR)
        .first()
    )
    if not admin_role or not editor_role:
        raise ValueError("ROLE_NOT_FOUND")

    admin_memberships = (
        db.query(TenantMembership)
        .join(TenantRole, TenantMembership.role_id == TenantRole.id)
        .filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.is_active.is_(True),
            TenantRole.code == SYSTEM_ROLE_ADMIN,
        )
        .all()
    )

    target.role_id = admin_role.id
    for membership in admin_memberships:
        if membership.user_id != new_admin_user_id:
            membership.role_id = editor_role.id

    db.commit()
