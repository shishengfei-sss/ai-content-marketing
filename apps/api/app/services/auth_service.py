"""认证与用户注册（一人一号）。

注册时创建 tenant + user，公司名称全平台唯一；登录支持手机号 + 密码。
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import uuid_eq
from app.models import Tenant, User
from app.services.membership_service import create_tenant_with_admin, list_active_memberships
from app.services.tenant_service import assert_tenant_name_available


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def register_user(
    db: Session,
    *,
    phone: str,
    password: str,
    industry_code: str = "finance",
    display_name: str = "",
    tenant_name: str,
) -> User:
    if db.query(User).filter(User.phone == phone).first():
        raise ValueError("PHONE_EXISTS")

    company_name = assert_tenant_name_available(db, tenant_name)

    user = User(
        tenant_id=None,
        phone=phone,
        email=None,
        hashed_password=hash_password(password),
        display_name=display_name or f"用户{phone[-4:]}",
        role="user",
        is_active=True,
    )
    db.add(user)
    db.flush()

    create_tenant_with_admin(
        db,
        name=company_name,
        industry_code=industry_code,
        user=user,
    )
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, phone: str, password: str) -> User | None:
    user = db.query(User).filter(User.phone == phone).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def get_active_user_by_phone(db: Session, phone: str) -> User | None:
    return (
        db.query(User)
        .filter(User.phone == phone, User.is_active.is_(True))
        .first()
    )


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return (
        db.query(User)
        .options(joinedload(User.tenant))
        .filter(uuid_eq(User.id, user_id))
        .first()
    )


def reset_user_password(db: Session, user_id: UUID, password: str) -> User:
    user = get_user_by_id(db, user_id)
    if not user:
        raise ValueError("NOT_FOUND")
    user.hashed_password = hash_password(password)
    db.commit()
    db.refresh(user)
    return user


def delete_user_account(db: Session, user_id: UUID, *, actor_id: UUID) -> None:
    """删除用户及其 Membership；保留 Tenant 与企业数据（FR-ADMIN-USER-06）。"""
    from app.models import Content, ContentReview, TenantMembership, UserPromptProfile

    user = db.query(User).filter(uuid_eq(User.id, user_id)).first()
    if not user:
        raise ValueError("NOT_FOUND")
    if user.id == actor_id:
        raise ValueError("CANNOT_DELETE_SELF")

    tenant_ids = {
        row[0]
        for row in db.query(TenantMembership.tenant_id)
        .filter(TenantMembership.user_id == user.id)
        .all()
    }

    for tenant_id in tenant_ids:
        successor = (
            db.query(TenantMembership)
            .filter(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_active.is_(True),
                TenantMembership.user_id != user.id,
            )
            .order_by(TenantMembership.joined_at.asc())
            .first()
        )
        if not successor:
            continue
        db.query(Content).filter(
            Content.tenant_id == tenant_id,
            Content.author_id == user.id,
        ).update({Content.author_id: successor.user_id}, synchronize_session=False)

    db.query(ContentReview).filter(ContentReview.reviewer_id == user.id).delete(
        synchronize_session=False
    )
    db.query(UserPromptProfile).filter(UserPromptProfile.user_id == user.id).delete(
        synchronize_session=False
    )
    db.query(TenantMembership).filter(TenantMembership.user_id == user.id).delete(
        synchronize_session=False
    )
    if user.tenant_id:
        user.tenant_id = None
    db.delete(user)
    db.commit()
