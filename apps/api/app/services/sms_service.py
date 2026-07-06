"""短信验证码（login / reset_password 场景隔离）。"""

import secrets
import time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User

_store: dict[str, dict[str, float | str]] = {}


def _now() -> float:
    return time.time()


def _key(phone: str, scene: str) -> str:
    return f"{phone}:{scene}"


def send_code(db: Session, phone: str, *, scene: str, require_registered: bool = True) -> dict[str, str | None]:
    user = (
        db.query(User)
        .filter(User.phone == phone, User.is_active.is_(True))
        .first()
    )
    if require_registered and not user:
        raise HTTPException(status_code=400, detail="若该手机号已注册，将发送验证码")
    if not require_registered and user is None:
        raise HTTPException(status_code=400, detail="若该手机号已注册，将发送验证码")

    store_key = _key(phone, scene)
    entry = _store.get(store_key)
    if entry and _now() - float(entry.get("last_sent_at", 0)) < settings.SMS_SEND_INTERVAL_SEC:
        raise HTTPException(status_code=429, detail="发送过于频繁，请稍后再试")

    if settings.SMS_PROVIDER == "mock":
        code = settings.SMS_MOCK_CODE
        mock_hint = f"测试环境验证码：{code}"
    else:
        code = f"{secrets.randbelow(900000) + 100000:06d}"
        mock_hint = None

    _store[store_key] = {
        "code": code,
        "expire_at": _now() + settings.SMS_CODE_EXPIRE_SEC,
        "last_sent_at": _now(),
    }
    return {"message": "验证码已发送", "mock_hint": mock_hint}


def verify_code(phone: str, code: str, *, scene: str) -> None:
    store_key = _key(phone, scene)
    entry = _store.get(store_key)
    if not entry:
        raise HTTPException(status_code=400, detail="请先获取验证码")
    if _now() > float(entry["expire_at"]):
        _store.pop(store_key, None)
        raise HTTPException(status_code=400, detail="验证码已过期")
    if str(entry["code"]) != code.strip():
        raise HTTPException(status_code=400, detail="验证码错误")
    _store.pop(store_key, None)


def send_login_code(db: Session, phone: str) -> dict[str, str | None]:
    return send_code(db, phone, scene="login", require_registered=True)


def verify_login_code(phone: str, code: str) -> None:
    verify_code(phone, code, scene="login")


def send_reset_password_code(db: Session, phone: str) -> dict[str, str | None]:
    user = (
        db.query(User)
        .filter(User.phone == phone, User.is_active.is_(True))
        .first()
    )
    if not user:
        raise HTTPException(status_code=400, detail="若该手机号已注册，将发送验证码")
    return send_code(db, phone, scene="reset_password", require_registered=True)


def verify_reset_password_code(phone: str, code: str) -> None:
    verify_code(phone, code, scene="reset_password")
