from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TenantMembership, User
from app.permissions import PLATFORM_ADMIN_ROLE
from app.services.auth_service import decode_access_token, get_user_by_id
from app.services.membership_service import get_membership, is_platform_admin

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
    return user


def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    try:
        return decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")


def get_active_tenant_id(
    payload: dict = Depends(get_token_payload),
    current_user: User = Depends(get_current_user),
) -> UUID | None:
    raw = payload.get("active_tenant_id")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")


def require_active_tenant_id(
    active_tenant_id: UUID | None = Depends(get_active_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UUID:
    if not active_tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请先选择公司")
    if is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="平台管理员请使用用户工作台")
    if not get_membership(db, current_user.id, active_tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该公司")
    return active_tenant_id


@dataclass
class TenantContext:
    user: User
    tenant_id: UUID
    membership: TenantMembership


def get_tenant_context(
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
) -> TenantContext:
    if is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="平台管理员请使用用户工作台")
    membership = get_membership(db, current_user.id, tenant_id)
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该公司")
    return TenantContext(user=current_user, tenant_id=tenant_id, membership=membership)


def require_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != PLATFORM_ADMIN_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要平台管理员权限")
    return current_user
