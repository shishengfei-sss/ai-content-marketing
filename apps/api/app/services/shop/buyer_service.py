"""买家身份：openid 登录 + mobile 归一。对照执行计划 M5-2。"""

from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models.shop import ShopBuyer
from app.schemas.shop_platform import BuyerOut
from app.services.auth_service import create_access_token


def mask_mobile(mobile: str | None) -> str | None:
    if not mobile:
        return None
    if "*" in mobile:
        return mobile
    if len(mobile) == 11:
        return f"{mobile[:3]}****{mobile[-4:]}"
    return "***"


def buyer_out(b: ShopBuyer) -> BuyerOut:
    return BuyerOut(
        id=b.id,
        tenant_id=b.tenant_id,
        mobile=b.mobile,
        mobile_masked=mask_mobile(b.mobile),
        wx_openid=b.wx_openid,
        nickname=b.nickname,
        avatar_url=b.avatar_url,
    )


def resolve_openid_from_code(code: str) -> str:
    """开发/验收：code 以 mock: 前缀时直接当 openid；否则用稳定派生。"""
    code = (code or "").strip()
    if not code:
        raise HTTPException(status_code=422, detail="code 不能为空")
    if code.startswith("mock:"):
        openid = code[5:].strip()
        if not openid:
            raise HTTPException(status_code=422, detail="mock openid 不能为空")
        return openid[:64]
    # stub：非 mock 也派生可重复 openid，便于联调
    return f"wx_{uuid.uuid5(uuid.NAMESPACE_URL, code).hex[:28]}"


def login_or_create(db: Session, tenant_id: UUID, code: str) -> tuple[str, ShopBuyer]:
    openid = resolve_openid_from_code(code)
    buyer = (
        db.query(ShopBuyer)
        .filter(uuid_eq(ShopBuyer.tenant_id, tenant_id), ShopBuyer.wx_openid == openid)
        .first()
    )
    if not buyer:
        buyer = ShopBuyer(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            wx_openid=openid,
            nickname=f"买家{openid[-4:]}",
        )
        db.add(buyer)
        db.commit()
        db.refresh(buyer)
    token = create_access_token(
        str(buyer.id),
        extra={"typ": "shop_buyer", "tenant_id": str(tenant_id), "buyer_id": str(buyer.id)},
    )
    return token, buyer


def bind_mobile(db: Session, buyer: ShopBuyer, mobile: str) -> ShopBuyer:
    if not mobile or len(mobile) != 11 or not mobile.isdigit():
        raise HTTPException(status_code=422, detail="手机号须为 11 位数字")
    existing = (
        db.query(ShopBuyer)
        .filter(
            uuid_eq(ShopBuyer.tenant_id, buyer.tenant_id),
            ShopBuyer.mobile == mobile,
            ShopBuyer.id != buyer.id,
        )
        .first()
    )
    if existing:
        # 合并：把当前 openid 并到已有 mobile 买家，删除空壳
        if buyer.wx_openid and not existing.wx_openid:
            existing.wx_openid = buyer.wx_openid
        elif buyer.wx_openid and existing.wx_openid and buyer.wx_openid != existing.wx_openid:
            # 已有 openid：保留 existing，当前 buyer 若无订单可删；简化为报错引导
            raise HTTPException(status_code=409, detail="该手机号已绑定其他微信账号")
        db.delete(buyer)
        db.commit()
        db.refresh(existing)
        return existing
    buyer.mobile = mobile
    db.commit()
    db.refresh(buyer)
    return buyer


def get_buyer(db: Session, buyer_id: UUID, tenant_id: UUID | None = None) -> ShopBuyer:
    q = db.query(ShopBuyer).filter(uuid_eq(ShopBuyer.id, buyer_id))
    if tenant_id is not None:
        q = q.filter(uuid_eq(ShopBuyer.tenant_id, tenant_id))
    b = q.first()
    if not b:
        raise HTTPException(status_code=401, detail="买家不存在或已失效")
    return b
