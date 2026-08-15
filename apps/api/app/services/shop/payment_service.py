"""支付配置 + 支付单 + 日志。对照执行计划 M3。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.shop import (
    ShopMerchantAccount,
    ShopPayment,
    ShopPaymentConfig,
    ShopPaymentLog,
    ShopStore,
)
from app.schemas.shop_platform import PaymentConfigOut, PaymentConfigUpsertRequest
from app.services.crypto import decrypt_api_key, encrypt_api_key, mask_api_key
def _now() -> datetime:
    return datetime.now(timezone.utc)


def write_payment_log(
    db: Session,
    *,
    tenant_id: UUID,
    order_id: UUID | None,
    event: str,
    request_json: dict | None = None,
    response_json: dict | None = None,
    status: str = "ok",
    error_msg: str | None = None,
    wx_transaction_id: str | None = None,
) -> ShopPaymentLog:
    log = ShopPaymentLog(
        id=uuid.uuid4(),
        order_id=order_id,
        tenant_id=tenant_id,
        event=event,
        wx_transaction_id=wx_transaction_id,
        request_json=request_json or {},
        response_json=response_json or {},
        status=status,
        error_msg=error_msg,
    )
    db.add(log)
    db.flush()
    return log


def get_active_config(db: Session, tenant_id: UUID, shop_id: UUID | None = None) -> ShopPaymentConfig | None:
    q = db.query(ShopPaymentConfig).filter(
        uuid_eq(ShopPaymentConfig.tenant_id, tenant_id),
        ShopPaymentConfig.status == "active",
    )
    if shop_id:
        q = q.filter(uuid_eq(ShopPaymentConfig.shop_id, shop_id))
    return q.order_by(ShopPaymentConfig.updated_at.desc()).first()


def require_active_config(db: Session, tenant_id: UUID, shop_id: UUID) -> ShopPaymentConfig:
    cfg = get_active_config(db, tenant_id, shop_id)
    if not cfg or not cfg.wx_api_key_encrypted:
        raise HTTPException(status_code=422, detail="请先配置微信支付参数")
    return cfg


def get_api_key(cfg: ShopPaymentConfig) -> str:
    return decrypt_api_key(cfg.wx_api_key_encrypted)


def _config_out(cfg: ShopPaymentConfig) -> PaymentConfigOut:
    plain = ""
    try:
        plain = decrypt_api_key(cfg.wx_api_key_encrypted)
    except Exception:
        plain = ""
    return PaymentConfigOut(
        id=cfg.id,
        tenant_id=cfg.tenant_id,
        shop_id=cfg.shop_id,
        wx_mch_id=cfg.wx_mch_id,
        wx_app_id=cfg.wx_app_id,
        wx_api_key_masked=mask_api_key(plain),
        wx_notify_url=cfg.wx_notify_url,
        status=cfg.status,
        onboarded_at=cfg.onboarded_at,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
    )


def get_or_list_config(db: Session, ctx: TenantContext) -> PaymentConfigOut | None:
    cfg = get_active_config(db, ctx.tenant_id)
    if not cfg:
        # 也返回 disabled
        cfg = (
            db.query(ShopPaymentConfig)
            .filter(uuid_eq(ShopPaymentConfig.tenant_id, ctx.tenant_id))
            .order_by(ShopPaymentConfig.updated_at.desc())
            .first()
        )
    return _config_out(cfg) if cfg else None


def upsert_config(db: Session, ctx: TenantContext, body: PaymentConfigUpsertRequest) -> PaymentConfigOut:
    merchant = (
        db.query(ShopMerchantAccount)
        .filter(uuid_eq(ShopMerchantAccount.tenant_id, ctx.tenant_id))
        .first()
    )
    if not merchant:
        raise HTTPException(status_code=404, detail="商家未入驻")
    shop = None
    if body.shop_id:
        shop = (
            db.query(ShopStore)
            .filter(uuid_eq(ShopStore.id, body.shop_id), uuid_eq(ShopStore.tenant_id, ctx.tenant_id))
            .first()
        )
        if not shop:
            raise HTTPException(status_code=404, detail="店铺不存在")
    else:
        from app.services.shop.product_service import ensure_default_shop as _eds

        shop = _eds(db, ctx.tenant_id, merchant)

    if not body.wx_mch_id or not body.wx_app_id or not body.wx_api_key:
        raise HTTPException(status_code=422, detail="mch_id / app_id / api_key 必填")

    cfg = (
        db.query(ShopPaymentConfig)
        .filter(
            uuid_eq(ShopPaymentConfig.tenant_id, ctx.tenant_id),
            uuid_eq(ShopPaymentConfig.shop_id, shop.id),
        )
        .first()
    )
    if not cfg:
        cfg = ShopPaymentConfig(
            id=uuid.uuid4(),
            merchant_id=merchant.id,
            tenant_id=ctx.tenant_id,
            shop_id=shop.id,
        )
        db.add(cfg)
    cfg.wx_mch_id = body.wx_mch_id.strip()
    cfg.wx_app_id = body.wx_app_id.strip()
    cfg.wx_api_key_encrypted = encrypt_api_key(body.wx_api_key.strip())
    cfg.wx_notify_url = body.wx_notify_url
    cfg.status = body.status or "active"
    cfg.onboarded_at = _now()
    cfg.onboarded_by = ctx.user.id
    db.commit()
    db.refresh(cfg)
    write_payment_log(
        db,
        tenant_id=ctx.tenant_id,
        order_id=None,
        event="config_upsert",
        request_json={"shop_id": str(shop.id), "wx_mch_id": cfg.wx_mch_id},
        response_json={"config_id": str(cfg.id), "status": cfg.status},
    )
    db.commit()
    return _config_out(cfg)


def test_config(db: Session, ctx: TenantContext) -> dict:
    cfg = get_active_config(db, ctx.tenant_id)
    if not cfg:
        raise HTTPException(status_code=422, detail="尚未保存支付配置")
    from app.services.shop.wechat_pay_service import wechat_pay_service

    key = get_api_key(cfg)
    prepay = wechat_pay_service.create_prepay(
        order_no=f"TEST{_now().strftime('%Y%m%d%H%M%S')}",
        amount_cents=1,
        description="配置联通测试",
        openid="mock_openid_test",
        wx_app_id=cfg.wx_app_id,
        wx_mch_id=cfg.wx_mch_id,
        api_key=key,
        notify_url=cfg.wx_notify_url,
    )
    write_payment_log(
        db,
        tenant_id=ctx.tenant_id,
        order_id=None,
        event="config_test",
        response_json={"prepay_id": prepay.get("prepay_id"), "mode": prepay.get("mode")},
    )
    db.commit()
    return {"ok": True, "mode": prepay.get("mode"), "prepay_id": prepay.get("prepay_id")}
