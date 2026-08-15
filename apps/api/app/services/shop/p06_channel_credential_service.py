"""P06 平台渠道凭据。对照 06#p06 · #p06a · #p06b · #p06c · #p06d · 04#platform_channel_credentials。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import User
from app.models.shop import PlatformChannelCredential, ShopChannelMapping, ShopPaymentOnboarding
from app.services.crypto import encrypt_api_key, decrypt_api_key
from app.services.shop.entitlement_service import TZ_SH

CHANNEL_DOUDIAN = "doudian"
CHANNEL_WECHAT = "wechat_pay_sp"
GRACE_HOURS = 24


def _now() -> datetime:
    return datetime.now(TZ_SH)


def _get_row(db: Session, channel: str) -> PlatformChannelCredential | None:
    return (
        db.query(PlatformChannelCredential)
        .filter(PlatformChannelCredential.channel == channel)
        .first()
    )


def _secrets(row: PlatformChannelCredential | None) -> dict:
    if not row or not row.secret_enc:
        return {}
    try:
        return json.loads(decrypt_api_key(row.secret_enc) or "{}")
    except Exception:
        return {}


def _write_secrets(row: PlatformChannelCredential, data: dict) -> None:
    row.secret_enc = encrypt_api_key(json.dumps(data, ensure_ascii=False))


def _operator_name(user: User) -> str:
    return (user.display_name or "").strip() or (user.phone or "平台管理员")


def _mask_tail(value: str | None, keep: int = 4) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    if len(s) <= keep:
        return "•" * len(s)
    return "•" * (len(s) - keep) + s[-keep:]


def _mask_mch(value: str | None) -> str:
    s = (value or "").strip()
    if len(s) < 4:
        return "•" * len(s) if s else ""
    return s[:2] + "*" * (len(s) - 4) + s[-2:]


def _parse_cert(pem: str) -> tuple[str, str | None]:
    text = (pem or "").strip()
    if "BEGIN CERTIFICATE" not in text:
        raise HTTPException(status_code=422, detail="证书解析失败")
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        cert = x509.load_pem_x509_certificate(text.encode("utf-8"), default_backend())
        serial = format(cert.serial_number, "X")
        exp = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after
        exp_s = exp.date().isoformat() if hasattr(exp, "date") else str(exp)[:10]
        return serial, exp_s
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="证书解析失败") from exc


def _require_channel_perm_configured(row: PlatformChannelCredential | None, empty_msg: str) -> PlatformChannelCredential:
    if not row or not _secrets(row):
        raise HTTPException(status_code=422, detail=empty_msg)
    return row


def mapping_count(db: Session) -> int:
    return db.query(ShopChannelMapping).count()


def wechat_sub_stats(db: Session) -> dict:
    rows = db.query(ShopPaymentOnboarding).all()
    approved = sum(1 for r in rows if r.onboarding_status == "approved")
    submitted = sum(1 for r in rows if r.onboarding_status == "submitted")
    return {"approved": approved, "submitted": submitted}


def channel_config(db: Session, base_url: str) -> dict:
    base = (base_url or "").rstrip("/")
    doudian = _get_row(db, CHANNEL_DOUDIAN)
    wechat = _get_row(db, CHANNEL_WECHAT)
    d_pub = dict((doudian.public_json if doudian else None) or {})
    w_pub = dict((wechat.public_json if wechat else None) or {})
    d_ok = bool(_secrets(doudian).get("app_secret"))
    w_ok = bool(_secrets(wechat).get("api_v3_key") and w_pub.get("cert_serial"))
    return {
        "doudian_webhook_url": f"{base}/api/v1/webhooks/douyin/order",
        "wechat_pay_notify_url": f"{base}/api/v1/mp/shop/payments/notify",
        "wechat_refund_notify_url": f"{base}/api/v1/webhooks/wechat-refund/notify",
        "credentials_persist": True,
        "doudian_configured": d_ok,
        "wechat_pay_configured": w_ok,
        "wechat_open_ticket_ok": False,
        "doudian_mapping_count": mapping_count(db),
        "wechat_sub_stats": wechat_sub_stats(db),
        "doudian": {
            "configured": d_ok,
            "app_key_masked": d_pub.get("app_key_masked") or "",
            "updated_at": doudian.updated_at.isoformat() if doudian and doudian.updated_at else None,
            "updated_by_name": d_pub.get("updated_by_name"),
            "last_tested_at": doudian.last_tested_at.isoformat() if doudian and doudian.last_tested_at else None,
            "last_test_ok": doudian.last_test_ok if doudian else None,
            "grace_until": doudian.grace_until.isoformat() if doudian and doudian.grace_until else None,
        },
        "wechat_pay": {
            "configured": w_ok,
            "mch_id_masked": w_pub.get("mch_id_masked") or "",
            "app_id_masked": w_pub.get("app_id_masked") or "",
            "cert_serial": w_pub.get("cert_serial") or "",
            "cert_expires": w_pub.get("cert_expires") or "",
            "platform_pub_configured": bool(w_pub.get("platform_pub")),
            "updated_at": wechat.updated_at.isoformat() if wechat and wechat.updated_at else None,
            "updated_by_name": w_pub.get("updated_by_name"),
            "last_tested_at": wechat.last_tested_at.isoformat() if wechat and wechat.last_tested_at else None,
            "last_test_ok": wechat.last_test_ok if wechat else None,
            "grace_until": wechat.grace_until.isoformat() if wechat and wechat.grace_until else None,
        },
    }


def _upsert(db: Session, channel: str) -> PlatformChannelCredential:
    row = _get_row(db, channel)
    if row:
        return row
    row = PlatformChannelCredential(id=uuid4(), channel=channel, public_json={})
    db.add(row)
    db.flush()
    return row


def save_doudian(db: Session, user: User, *, app_key: str, app_secret: str | None, base_url: str = "") -> dict:
    key = (app_key or "").strip()
    if len(key) < 8:
        raise HTTPException(status_code=422, detail="AppKey 格式错误")
    row = _upsert(db, CHANNEL_DOUDIAN)
    secrets = _secrets(row)
    secret = (app_secret or "").strip()
    if secret:
        secrets["app_secret"] = secret
    elif not secrets.get("app_secret"):
        raise HTTPException(status_code=422, detail="AppKey 格式错误")
    secrets["app_key"] = key
    _write_secrets(row, secrets)
    pub = dict(row.public_json or {})
    pub.update(
        {
            "app_key_masked": _mask_tail(key),
            "updated_by_name": _operator_name(user),
        }
    )
    row.public_json = pub
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return channel_config(db, base_url)


def rotate_doudian(db: Session, user: User, *, app_secret: str, base_url: str = "") -> dict:
    row = _require_channel_perm_configured(_get_row(db, CHANNEL_DOUDIAN), "请先完成首次配置")
    secret = (app_secret or "").strip()
    if len(secret) < 8:
        raise HTTPException(status_code=422, detail="AppKey 格式错误")
    old = row.secret_enc
    secrets = _secrets(row)
    secrets["app_secret"] = secret
    _write_secrets(row, secrets)
    row.prev_secret_enc = old
    row.grace_until = _now() + timedelta(hours=GRACE_HOURS)
    pub = dict(row.public_json or {})
    pub["updated_by_name"] = _operator_name(user)
    row.public_json = pub
    row.updated_by = user.id
    db.commit()
    return channel_config(db, base_url)


def test_doudian(db: Session, user: User, *, base_url: str = "") -> dict:
    row = _require_channel_perm_configured(_get_row(db, CHANNEL_DOUDIAN), "请先保存配置")
    secrets = _secrets(row)
    ok = bool(secrets.get("app_key") and secrets.get("app_secret"))
    row.last_tested_at = _now()
    row.last_test_ok = ok
    row.updated_by = user.id
    db.commit()
    if not ok:
        raise HTTPException(status_code=422, detail="请先保存配置")
    return channel_config(db, base_url)


def save_wechat(
    db: Session,
    user: User,
    *,
    mch_id: str,
    app_id: str,
    api_v3_key: str | None,
    cert_pem: str | None = None,
    cert_key: str | None = None,
    platform_pub: str | None = None,
    base_url: str = "",
) -> dict:
    mch = (mch_id or "").strip()
    aid = (app_id or "").strip()
    if len(mch) < 8 or len(aid) < 8:
        raise HTTPException(status_code=422, detail="服务商商户号与 AppID 不能为空")
    row = _upsert(db, CHANNEL_WECHAT)
    secrets = _secrets(row)
    v3 = (api_v3_key or "").strip()
    if v3:
        if len(v3) != 32:
            raise HTTPException(status_code=422, detail="v3 密钥长度须 32 位")
        secrets["api_v3_key"] = v3
    elif not secrets.get("api_v3_key"):
        raise HTTPException(status_code=422, detail="v3 密钥长度须 32 位")
    pem = (cert_pem or "").strip()
    key = (cert_key or "").strip()
    pub = dict(row.public_json or {})
    if pem or key:
        if not pem or not key:
            raise HTTPException(status_code=422, detail="证书解析失败")
        serial, expires = _parse_cert(pem)
        secrets["cert_pem"] = pem
        secrets["cert_key"] = key
        pub["cert_serial"] = serial
        pub["cert_expires"] = expires
    if not pub.get("cert_serial"):
        raise HTTPException(status_code=422, detail="请先上传 API 证书")
    if platform_pub is not None:
        text = platform_pub.strip()
        if text:
            secrets["platform_pub"] = text
            pub["platform_pub"] = True
    secrets["mch_id"] = mch
    secrets["app_id"] = aid
    _write_secrets(row, secrets)
    pub.update(
        {
            "mch_id_masked": _mask_mch(mch),
            "app_id_masked": _mask_tail(aid),
            "updated_by_name": _operator_name(user),
        }
    )
    row.public_json = pub
    row.updated_by = user.id
    db.commit()
    return channel_config(db, base_url)


def rotate_wechat_cert(db: Session, user: User, *, cert_pem: str, cert_key: str, base_url: str = "") -> dict:
    row = _require_channel_perm_configured(_get_row(db, CHANNEL_WECHAT), "请先保存配置")
    pem = (cert_pem or "").strip()
    key = (cert_key or "").strip()
    if not pem or not key:
        raise HTTPException(status_code=422, detail="证书解析失败")
    serial, expires = _parse_cert(pem)
    old = row.secret_enc
    secrets = _secrets(row)
    secrets["cert_pem"] = pem
    secrets["cert_key"] = key
    _write_secrets(row, secrets)
    row.prev_secret_enc = old
    row.grace_until = _now() + timedelta(hours=GRACE_HOURS)
    pub = dict(row.public_json or {})
    pub["cert_serial"] = serial
    pub["cert_expires"] = expires
    pub["updated_by_name"] = _operator_name(user)
    row.public_json = pub
    row.updated_by = user.id
    db.commit()
    return channel_config(db, base_url)


def rotate_wechat_v3(db: Session, user: User, *, api_v3_key: str, base_url: str = "") -> dict:
    row = _require_channel_perm_configured(_get_row(db, CHANNEL_WECHAT), "请先保存配置")
    v3 = (api_v3_key or "").strip()
    if len(v3) != 32:
        raise HTTPException(status_code=422, detail="v3 密钥长度须 32 位")
    old = row.secret_enc
    secrets = _secrets(row)
    secrets["api_v3_key"] = v3
    _write_secrets(row, secrets)
    row.prev_secret_enc = old
    row.grace_until = _now() + timedelta(hours=GRACE_HOURS)
    pub = dict(row.public_json or {})
    pub["updated_by_name"] = _operator_name(user)
    row.public_json = pub
    row.updated_by = user.id
    db.commit()
    return channel_config(db, base_url)


def test_wechat(db: Session, user: User, *, base_url: str = "") -> dict:
    row = _require_channel_perm_configured(_get_row(db, CHANNEL_WECHAT), "请先保存配置")
    secrets = _secrets(row)
    pub = dict(row.public_json or {})
    ok = bool(secrets.get("api_v3_key") and secrets.get("mch_id") and pub.get("cert_serial"))
    row.last_tested_at = _now()
    row.last_test_ok = ok
    row.updated_by = user.id
    db.commit()
    if not ok:
        raise HTTPException(status_code=422, detail="请先保存配置")
    return channel_config(db, base_url)
