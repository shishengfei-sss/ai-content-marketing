"""买家端 JWT 依赖（typ=shop_buyer）。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.shop import ShopBuyer
from app.services.auth_service import decode_access_token
from app.services.shop.buyer_service import get_buyer

security = HTTPBearer(auto_error=False)


@dataclass
class BuyerContext:
    buyer: ShopBuyer
    tenant_id: UUID


def resolve_buyer_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    access_token: str | None = Query(default=None, description="供 video/audio 等无法带 Header 的资源请求"),
) -> str | None:
    if credentials and credentials.credentials:
        return credentials.credentials
    if access_token and str(access_token).strip():
        return str(access_token).strip()
    return None


def _parse_buyer_token(
    token: str | None,
    db: Session,
) -> BuyerContext | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except JWTError:
        return None
    if payload.get("typ") != "shop_buyer":
        return None
    try:
        buyer_id = UUID(str(payload.get("buyer_id") or payload.get("sub")))
        tenant_id = UUID(str(payload["tenant_id"]))
    except (KeyError, ValueError, TypeError):
        return None
    try:
        buyer = get_buyer(db, buyer_id, tenant_id)
    except HTTPException:
        return None
    return BuyerContext(buyer=buyer, tenant_id=tenant_id)


def get_buyer_context(
    token: str | None = Depends(resolve_buyer_access_token),
    db: Session = Depends(get_db),
) -> BuyerContext:
    bctx = _parse_buyer_token(token, db)
    if not bctx:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    return bctx


def get_optional_buyer_context(
    token: str | None = Depends(resolve_buyer_access_token),
    db: Session = Depends(get_db),
) -> BuyerContext | None:
    return _parse_buyer_token(token, db)
