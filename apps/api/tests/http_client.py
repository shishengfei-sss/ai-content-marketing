"""测试 HTTP 客户端：优先 TestClient，可选连 live API。"""
from __future__ import annotations

import json
import os
import subprocess
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
    def _parse_body(status: int, raw_bytes: bytes):
        if not raw_bytes:
            return status, {}
        # csv 可能带 UTF-8 BOM；xlsx 等二进制用 replace 避免崩，验收脚本多半只看 status
        raw = raw_bytes.decode("utf-8-sig", errors="replace")
        if not raw.strip():
            return status, {}
        try:
            return status, json.loads(raw)
        except json.JSONDecodeError:
            return status, raw

    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            return _parse_body(resp.status, resp.read())
    except urllib.error.HTTPError as e:
        return _parse_body(e.code, e.read())


def req_upload(
    path: str,
    token: str,
    fields: dict,
    *,
    filename: str = "upload.png",
    content: bytes = b"\x89PNG\r\n\x1a\nfake",
    content_type: str = "image/png",
    file_field: str = "file",
):
    """multipart 上传（入驻材料等）。"""
    full_path = path if path.startswith(PREFIX) else PREFIX + path
    headers = {"Authorization": f"Bearer {token}"}
    files = {file_field: (filename, content, content_type)}
    if not USE_LIVE:
        client = _get_test_client()
        r = client.post(full_path, headers=headers, data=fields, files=files)
        try:
            data = r.json()
        except Exception:
            data = r.text if (r.text or "").strip() else {}
        return r.status_code, data

    import httpx

    url = BASE + (path if path.startswith("/") else "/" + path)
    if path.startswith(PREFIX):
        url = BASE.removesuffix("/api/v1").rstrip("/") + path
    r = httpx.post(url, headers=headers, data=fields, files=files, timeout=120)
    try:
        data = r.json()
    except Exception:
        data = r.text if (r.text or "").strip() else {}
    return r.status_code, data


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
            row.model = settings.DEEPSEEK_MODEL or "deepseek-v4-flash"
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
        "model": settings.DEEPSEEK_MODEL or "deepseek-v4-flash",
        "is_active": True,
    }
    if settings.DEEPSEEK_API_KEY:
        body["api_key"] = settings.DEEPSEEK_API_KEY
    req("PATCH", "/admin/platform-llm", token=admin_token, body=body)


def captured_run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Windows 控制台默认 GBK，pytest/alembic 输出含 UTF-8 时 text=True 会崩。"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        args,
        cwd=cwd or API_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def admin_users(token: str, q: str | None = None, page_size: int = 100) -> tuple[int, list]:
    """平台账号列表已分页；按手机号/关键词查 items。"""
    qs = f"page=1&page_size={page_size}"
    if q:
        qs += f"&q={quote(q)}"
    code, data = req("GET", f"/admin/users?{qs}", token=token)
    if isinstance(data, list):
        return code, data
    if isinstance(data, dict):
        return code, list(data.get("items") or [])
    return code, []


def run_nested_script(label: str, script: str) -> bool:
    """套件已按序跑过前序脚本时跳过链式回归（与 SKIP_NESTED_M0_M8 同开关）。"""
    if os.environ.get("VERIFY_SKIP_NESTED_M0_M8") == "1":
        return check(label, True, "skipped nested")
    proc = subprocess.run([sys.executable, "-B", str(API_ROOT / "tests" / script)], cwd=API_ROOT)
    return check(label, proc.returncode == 0, f"exit={proc.returncode}")


def run_nested_m0_m8(label: str) -> bool:
    """子脚本内的 M0～M8 回归。套件入口已跑过时设 VERIFY_SKIP_NESTED_M0_M8=1。"""
    if os.environ.get("VERIFY_SKIP_NESTED_M0_M8") == "1":
        return check(label, True, "skipped nested")
    proc = subprocess.run([sys.executable, "-B", str(API_ROOT / "tests" / "run_m0_m8.py")], cwd=API_ROOT)
    return check(label, proc.returncode == 0, f"exit={proc.returncode}")
