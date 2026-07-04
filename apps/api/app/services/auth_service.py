"""认证与用户注册（一人一号）。

注册时创建 tenant + user，租户名默认用手机号；登录支持手机号 + 密码。
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
) -> User:
    if db.query(User).filter(User.phone == phone).first():
        raise ValueError("PHONE_EXISTS")

    tenant = Tenant(name=phone, industry_code=industry_code)
    db.add(tenant)
    db.flush()

    user = User(
        tenant_id=tenant.id,
        phone=phone,
        email=None,
        hashed_password=hash_password(password),
        display_name=display_name or f"用户{phone[-4:]}",
        role="user",
        is_active=True,
    )
    db.add(user)
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
    """删除用户及其租户下的全部数据（一人一号）。"""
    from app.models import (
        Content,
        ContentReview,
        ExportRecord,
        KnowledgeChunk,
        KnowledgeDocument,
        LLMConfig,
        PlatformAccount,
        PublishLog,
        Tenant,
        TenantBrandProfile,
        UserPromptProfile,
    )

    user = db.query(User).filter(uuid_eq(User.id, user_id)).first()
    if not user:
        raise ValueError("NOT_FOUND")
    if user.id == actor_id:
        raise ValueError("CANNOT_DELETE_SELF")

    tenant_id = user.tenant_id
    content_ids = [
        row[0]
        for row in db.query(Content.id).filter(Content.tenant_id == tenant_id).all()
    ]

    if content_ids:
        db.query(ContentReview).filter(ContentReview.content_id.in_(content_ids)).delete(
            synchronize_session=False
        )
        db.query(ExportRecord).filter(ExportRecord.content_id.in_(content_ids)).delete(
            synchronize_session=False
        )
        db.query(PublishLog).filter(PublishLog.content_id.in_(content_ids)).delete(
            synchronize_session=False
        )

    db.query(Content).filter(Content.tenant_id == tenant_id).delete(synchronize_session=False)
    db.query(UserPromptProfile).filter(UserPromptProfile.user_id == user.id).delete(
        synchronize_session=False
    )

    doc_ids = [
        row[0]
        for row in db.query(KnowledgeDocument.id)
        .filter(KnowledgeDocument.tenant_id == tenant_id)
        .all()
    ]
    if doc_ids:
        db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
    db.query(KnowledgeDocument).filter(KnowledgeDocument.tenant_id == tenant_id).delete(
        synchronize_session=False
    )

    db.query(LLMConfig).filter(LLMConfig.tenant_id == tenant_id).delete(synchronize_session=False)
    db.query(TenantBrandProfile).filter(TenantBrandProfile.tenant_id == tenant_id).delete(
        synchronize_session=False
    )
    db.query(PlatformAccount).filter(PlatformAccount.tenant_id == tenant_id).delete(
        synchronize_session=False
    )
    db.query(PublishLog).filter(PublishLog.tenant_id == tenant_id).delete(synchronize_session=False)
    db.query(ExportRecord).filter(ExportRecord.tenant_id == tenant_id).delete(
        synchronize_session=False
    )

    db.delete(user)
    db.query(Tenant).filter(Tenant.id == tenant_id).delete(synchronize_session=False)
    db.commit()
