"""LLM API Key 加解密与界面脱敏。

租户 llm_configs 表中的密钥 Fernet 加密存储；设置页展示 mask 后的值。
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.LLM_ENCRYPTION_KEY.encode()).digest()
    )
    return Fernet(key)


def encrypt_api_key(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    if not encrypted:
        return ""
    return _fernet().decrypt(encrypted.encode()).decode()


def decrypt_api_key_or_empty(encrypted: str) -> str:
    """解密失败（密钥轮换/脏数据）时返回空串，便于页面加载并重新保存 Key。"""
    if not encrypted:
        return ""
    try:
        return decrypt_api_key(encrypted)
    except InvalidToken:
        return ""


def mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}****{key[-4:]}"
