"""平台后台：企业管理与管理员转移。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import uuid_eq
from app.models import Tenant, TenantMembership, TenantRole, User
from app.permissions import SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_EDITOR
from app.services.membership_service import get_membership
from app.services.platform_llm_service import get_quota_status

logger = logging.getLogger(__name__)


def _tenant_fallback(tenant: Tenant) -> dict:
    return {
        "id": tenant.id,
        "name": tenant.name or "",
        "credit_code": tenant.credit_code,
        "industry_code": tenant.industry_code or "finance",
        "member_count": 0,
        "admin_summaries": [],
        "quota_used": 0,
        "quota_limit": 0,
        "created_at": tenant.created_at or datetime.now(timezone.utc),
    }


def _tenant_to_dict(db: Session, tenant: Tenant) -> dict:
    member_count = (
        db.query(func.count(TenantMembership.id))
        .filter(
            uuid_eq(TenantMembership.tenant_id, tenant.id),
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
            uuid_eq(TenantMembership.tenant_id, tenant.id),
            TenantMembership.is_active.is_(True),
            TenantRole.code == SYSTEM_ROLE_ADMIN,
        )
        .all()
    )
    try:
        quota = get_quota_status(db, tenant.id)
        quota_used = int(quota.get("used_count") or 0)
        quota_limit = int(quota.get("quota_limit") or 0)
    except Exception:
        logger.exception("tenant quota failed id=%s", tenant.id)
        quota_used, quota_limit = 0, 0
    return {
        "id": tenant.id,
        "name": tenant.name or "",
        "credit_code": tenant.credit_code,
        "industry_code": tenant.industry_code or "finance",
        "member_count": member_count,
        "admin_summaries": [
            {
                "user_id": row.user_id,
                "phone": row.user.phone if row.user else None,
                "display_name": ((row.user.display_name if row.user else None) or ""),
            }
            for row in admin_rows
            if row.user is not None
        ],
        "quota_used": quota_used,
        "quota_limit": quota_limit,
        "created_at": tenant.created_at or datetime.now(timezone.utc),
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
        try:
            items.append(_tenant_to_dict(db, tenant))
        except Exception:
            logger.exception("tenant list item failed id=%s", tenant.id)
            items.append(_tenant_fallback(tenant))
    return items, total


def get_tenant_admin(db: Session, tenant_id: UUID) -> dict | None:
    tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, tenant_id)).first()
    if not tenant:
        return None
    try:
        return _tenant_to_dict(db, tenant)
    except Exception:
        logger.exception("tenant detail failed id=%s", tenant_id)
        return _tenant_fallback(tenant)


def list_tenant_members_admin(db: Session, tenant_id: UUID) -> list[dict]:
    rows = (
        db.query(TenantMembership)
        .options(
            joinedload(TenantMembership.user),
            joinedload(TenantMembership.role),
        )
        .filter(uuid_eq(TenantMembership.tenant_id, tenant_id))
        .order_by(TenantMembership.joined_at.asc())
        .all()
    )
    out: list[dict] = []
    for row in rows:
        if not row.user or not row.role:
            continue
        out.append(
            {
                "membership_id": row.id,
                "user_id": row.user_id,
                "phone": row.user.phone,
                "display_name": row.user.display_name or "",
                "role_code": row.role.code,
                "role_name": row.role.name,
                "membership_active": row.is_active,
                "user_active": bool(row.user.is_active),
                "joined_at": row.joined_at,
            }
        )
    return out


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
