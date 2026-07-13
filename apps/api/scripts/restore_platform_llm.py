#!/usr/bin/env python3
"""将平台 LLM 从 fake 恢复为 deepseek（人工 UAT / 日常开发用）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import req, reset_test_client, restore_platform_deepseek


def main() -> int:
    reset_test_client()
    code, data = req(
        "POST",
        "/auth/login",
        body={"phone": "13800000000", "password": "admin123456"},
    )
    if code != 200:
        print("admin login failed", code, data)
        return 1
    restore_platform_deepseek(data["access_token"], force=True)
    code2, cfg = req("GET", "/admin/platform-llm", token=data["access_token"])
    print("platform-llm:", cfg if code2 == 200 else code2)
    if code2 == 200 and cfg.get("provider") == "deepseek":
        masked = cfg.get("api_key_masked") or ""
        if masked in ("", "****") and not os.environ.get("DEEPSEEK_API_KEY"):
            print("已恢复 deepseek，但 API Key 仍为空：请在管理后台「平台 AI」填写 DeepSeek Key")
            return 1
        print("已恢复 deepseek，请刷新创作页重试")
        return 0
    print("恢复可能未生效，请检查管理后台平台 AI 配置")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
