"""测试 HTTP 客户端：优先 TestClient，可选连 live API。"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit, quote

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

USE_LIVE = os.environ.get("VERIFY_LIVE_API", "0") == "1"
if not USE_LIVE:
    os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
    from app.config import settings as _settings

    _settings.SMS_SEND_INTERVAL_SEC = 0
BASE = os.environ.get("VERIFY_API_BASE", "http://127.0.0.1:8000/api/v1")

_client = None


def reset_test_client() -> None:
    global _client
    _client = None


def _get_test_client():
    global _client
    if _client is None:
        from fastapi.testclient import TestClient
        from app.main import app

        _client = TestClient(app)
    return _client


PREFIX = "/api/v1"


def req(method: str, path: str, token: str | None = None, body: dict | None = None):
    full_path = path if path.startswith(PREFIX) else PREFIX + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if not USE_LIVE:
        client = _get_test_client()
        if method == "GET":
            r = client.get(full_path, headers=headers)
        elif method == "POST":
            r = client.post(full_path, headers=headers, json=body)
        elif method == "PATCH":
            r = client.patch(full_path, headers=headers, json=body)
        elif method == "PUT":
            r = client.put(full_path, headers=headers, json=body)
        elif method == "DELETE":
            r = client.delete(full_path, headers=headers)
        else:
            raise ValueError(method)
        try:
            data = r.json()
        except Exception:
            data = r.text if (r.text or "").strip() else {}
        return r.status_code, data

    url = BASE + path if path.startswith("/api/") else BASE + path
    parts = urlsplit(url)
    if parts.query:
        url = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(parse_qsl(parts.query, keep_blank_values=True), quote_via=quote),
                parts.fragment,
            )
        )
    data_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            raw = resp.read().decode()
            if not raw.strip():
                return resp.status, {}
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        if not raw.strip():
            return e.code, {}
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = raw
        return e.code, detail


def check(name: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def reset_all_tenant_quotas() -> None:
    """验收前重置租户 LLM 已用额度，避免多次跑全量脚本后 quota 耗尽。"""
    from app.database import SessionLocal
    from app.models import TenantLLMUsage

    db = SessionLocal()
    try:
        db.query(TenantLLMUsage).update({TenantLLMUsage.used_count: 0})
        db.commit()
    finally:
        db.close()


def clear_sms_rate_limits() -> None:
    """清除内存短信频控，避免同进程连跑 M5/M6/M8 时 forgot send-code 429。"""
    from app.config import settings
    from app.services import sms_service

    settings.SMS_SEND_INTERVAL_SEC = 0
    sms_service._store.clear()


def ensure_fake_platform(admin_token: str) -> None:
    """仅 FORCE_FAKE_PLATFORM_LLM=1 时写入 fake（CI/离线验收）；否则不覆盖真实配置。"""
    if os.environ.get("FORCE_FAKE_PLATFORM_LLM") != "1":
        return
    req(
        "PATCH",
        "/admin/platform-llm",
        token=admin_token,
        body={
            "provider": "fake",
            "base_url": "http://fake.local",
            "model": "fake-model",
            "api_key": "fake-key",
            "is_active": True,
        },
    )


def restore_platform_deepseek(admin_token: str, *, force: bool = False) -> None:
    """验收后恢复平台 DeepSeek。

    - 若 .env 提供了 DEEPSEEK_API_KEY（CI 场景）：用 env Key 覆盖。
    - 否则（本地开发，Key 在管理后台填写）：保留数据库中已有的加密 Key，
      不再清空，避免每次跑回归脚本都把用户在 UI 填的 Key 抹掉。
    """
    if not force and os.environ.get("FORCE_FAKE_PLATFORM_LLM") == "1":
        return
    from app.config import settings
    from app.database import SessionLocal
    from app.models import PlatformLLMConfig
    from app.services.crypto import encrypt_api_key

    db = SessionLocal()
    try:
        row = db.query(PlatformLLMConfig).order_by(PlatformLLMConfig.updated_at.desc()).first()
        if row:
            row.provider = "deepseek"
            row.base_url = settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com"
            row.model = settings.DEEPSEEK_MODEL or "deepseek-chat"
            row.is_active = True
            if settings.DEEPSEEK_API_KEY:
                row.api_key_encrypted = encrypt_api_key(settings.DEEPSEEK_API_KEY)
            # 无 env Key 时保留既有 api_key_encrypted，不再清空
            db.commit()
    finally:
        db.close()

    body: dict = {
        "provider": "deepseek",
        "base_url": settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com",
        "model": settings.DEEPSEEK_MODEL or "deepseek-chat",
        "is_active": True,
    }
    if settings.DEEPSEEK_API_KEY:
        body["api_key"] = settings.DEEPSEEK_API_KEY
    req("PATCH", "/admin/platform-llm", token=admin_token, body=body)
