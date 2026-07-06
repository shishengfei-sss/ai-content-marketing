"""测试数据修复：避免里程碑脚本互相污染。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Tenant, TenantMembership, User
from app.services.membership_service import list_active_memberships, seed_tenant_roles


def restore_single_company_user(db: Session, phone: str = "13900000099") -> None:
    """确保指定用户仅保留最早加入的一家公司（用于 M2/M6 单公司用例）。"""
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        return
    memberships = list_active_memberships(db, user.id)
    if len(memberships) <= 1:
        return
    primary = min(memberships, key=lambda m: m.joined_at)
    for membership in memberships:
        if membership.id != primary.id:
            db.delete(membership)
    user.tenant_id = primary.tenant_id
    db.commit()


def ensure_multi_tenant_user(db: Session, phone: str, password: str) -> str:
    """确保用户有两家公司，返回第二家 tenant_id。"""
    from app.services.auth_service import hash_password

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        user = User(
            phone=phone,
            hashed_password=hash_password(password),
            display_name="M2测试",
            role="user",
            is_active=True,
        )
        db.add(user)
        db.flush()
        tenant_a = Tenant(name="甲公司M2", industry_code="finance")
        db.add(tenant_a)
        db.flush()
        admin_a, _ = seed_tenant_roles(db, tenant_a.id)
        db.add(
            TenantMembership(
                user_id=user.id,
                tenant_id=tenant_a.id,
                role_id=admin_a.id,
                is_active=True,
            )
        )
        user.tenant_id = tenant_a.id
        db.flush()

    memberships = list_active_memberships(db, user.id)
    if len(memberships) < 2:
        tenant_b = Tenant(name="乙公司M2", industry_code="finance")
        db.add(tenant_b)
        db.flush()
        _admin_b, editor_b = seed_tenant_roles(db, tenant_b.id)
        db.add(
            TenantMembership(
                user_id=user.id,
                tenant_id=tenant_b.id,
                role_id=editor_b.id,
                is_active=True,
            )
        )
        db.flush()
        tenant_b_id = str(tenant_b.id)
    else:
        tenant_b_id = str(memberships[1].tenant_id)
    db.commit()
    return tenant_b_id
