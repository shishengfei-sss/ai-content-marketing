"""Diagnose DeepSeek key: .env vs DB vs live API (no full key print)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
os.chdir(API_ROOT)

from dotenv import load_dotenv

load_dotenv(API_ROOT / ".env")


def mask(k: str) -> str:
    k = (k or "").strip()
    if not k:
        return "(empty)"
    if len(k) <= 10:
        return f"len={len(k)}"
    return f"len={len(k)} {k[:6]}...{k[-4:]}"


def main() -> int:
    from app.config import settings
    from app.database import SessionLocal
    from app.models import PlatformLLMConfig
    from app.services.platform_llm_service import resolve_platform_api_key

    env_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    settings_key = (settings.DEEPSEEK_API_KEY or "").strip()
    llm_key = (settings.LLM_API_KEY or "").strip()
    print("env DEEPSEEK_API_KEY:", mask(env_key))
    print("settings.DEEPSEEK_API_KEY:", mask(settings_key))
    print("settings.LLM_API_KEY:", mask(llm_key))
    print("model:", settings.DEEPSEEK_MODEL)
    print("base:", settings.DEEPSEEK_BASE_URL)

    db = SessionLocal()
    try:
        row = db.query(PlatformLLMConfig).order_by(PlatformLLMConfig.updated_at.desc()).first()
        if not row:
            print("DB PlatformLLMConfig: (none)")
            resolved = settings_key or llm_key
        else:
            print(
                "DB platform:",
                f"provider={row.provider}",
                f"model={row.model}",
                f"active={row.is_active}",
                f"has_encrypted={bool(row.api_key_encrypted)}",
            )
            resolved = resolve_platform_api_key(row)
            print("resolved platform key:", mask(resolved))
            print("resolved == env:", resolved == env_key)
            print("resolved == settings:", resolved == settings_key)
    finally:
        db.close()

    if not resolved:
        print("TEST: no key to test")
        return 1

    import httpx

    url = (settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com").rstrip("/") + "/chat/completions"
    model = settings.DEEPSEEK_MODEL or "deepseek-v4-flash"
    try:
        r = httpx.post(
            url,
            headers={"Authorization": f"Bearer {resolved}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 8,
            },
            timeout=30.0,
        )
        print("LIVE status:", r.status_code)
        body = r.text[:300]
        print("LIVE body:", body)
        if r.status_code == 200:
            print("RESULT: key OK")
            return 0
        print("RESULT: key FAIL")
        return 2
    except Exception as e:
        print("LIVE error:", type(e).__name__, e)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
