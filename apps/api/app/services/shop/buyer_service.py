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


def is_claim_stub_openid(openid: str | None) -> bool:
    """领权页 H5/Mock 会话 openid（mock:claim_xxx → claim_xxx）。"""
    o = (openid or "").strip()
    return bool(o and o.startswith("claim_"))


def is_demo_rebind_openid(openid: str | None) -> bool:
    """演示/领权临时 openid（demo_buyer_paid、claim_*），领权绑手机时可合并。"""
    o = (openid or "").strip()
    return is_claim_stub_openid(o) or o.startswith("demo_")


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


def reassign_buyer_owned_rows(db: Session, from_buyer_id: UUID, to_buyer_id: UUID) -> None:
    """合并买家前把订单/权益/履约记录挂到目标买家，避免核销码孤儿。"""
    if from_buyer_id == to_buyer_id:
        return
    from app.models.shop import (
        ShopBooking,
        ShopClaimToken,
        ShopDigitalDownload,
        ShopEnrollment,
        ShopEntitlement,
        ShopInvoiceRequest,
        ShopLessonProgress,
        ShopOrder,
        ShopVerification,
    )

    for model, col in (
        (ShopOrder, ShopOrder.buyer_id),
        (ShopEntitlement, ShopEntitlement.buyer_id),
        (ShopBooking, ShopBooking.buyer_id),
        (ShopVerification, ShopVerification.buyer_id),
        (ShopLessonProgress, ShopLessonProgress.buyer_id),
        (ShopEnrollment, ShopEnrollment.buyer_id),
        (ShopDigitalDownload, ShopDigitalDownload.buyer_id),
        (ShopInvoiceRequest, ShopInvoiceRequest.buyer_id),
    ):
        db.query(model).filter(uuid_eq(col, from_buyer_id)).update({col: to_buyer_id}, synchronize_session=False)
    db.query(ShopOrder).filter(uuid_eq(ShopOrder.claimed_buyer_id, from_buyer_id)).update(
        {ShopOrder.claimed_buyer_id: to_buyer_id}, synchronize_session=False
    )
    db.query(ShopClaimToken).filter(uuid_eq(ShopClaimToken.claimed_buyer_id, from_buyer_id)).update(
        {ShopClaimToken.claimed_buyer_id: to_buyer_id}, synchronize_session=False
    )
    db.flush()


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
        openid_to_transfer = buyer.wx_openid
        if openid_to_transfer and not existing.wx_openid:
            buyer.wx_openid = None
            db.flush()
            existing.wx_openid = openid_to_transfer
        elif (
            openid_to_transfer
            and existing.wx_openid
            and openid_to_transfer != existing.wx_openid
        ):
            if is_demo_rebind_openid(existing.wx_openid):
                buyer.wx_openid = None
                db.flush()
                existing.wx_openid = openid_to_transfer
            else:
                raise HTTPException(status_code=409, detail="该手机号已绑定其他微信账号")
        reassign_buyer_owned_rows(db, buyer.id, existing.id)
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
