from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session, joinedload

from app.config import settings
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


def register_tenant(
    db: Session,
    *,
    company_name: str,
    email: str,
    password: str,
    industry_code: str = "finance",
    display_name: str = "",
) -> User:
    if db.query(User).filter(User.email == email).first():
        raise ValueError("EMAIL_EXISTS")

    tenant = Tenant(name=company_name, industry_code=industry_code)
    db.add(tenant)
    db.flush()

    user = User(
        tenant_id=tenant.id,
        email=email,
        hashed_password=hash_password(password),
        display_name=display_name or email.split("@")[0],
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return (
        db.query(User)
        .options(joinedload(User.tenant))
        .filter(User.id == user_id)
        .first()
    )
