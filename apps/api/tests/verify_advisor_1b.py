#!/usr/bin/env python3
"""v0.6 Phase B 验收：预检 input_class / clarify（TADV-TOPIC-04/05）。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ["VERIFY_LIVE_API"] = "0"

from tests.http_client import check, req, ensure_fake_platform


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def preflight(token: str, sid: str, message: str) -> tuple[int, dict]:
    return req(
        "POST",
        f"/agent/sessions/{sid}/preflight",
        token=token,
        body={
            "message": message,
            "platform": "wechat",
            "content_format": "article",
            "llm_source": "platform",
        },
    )


def step_1b_clarify(results: list[bool]) -> None:
    pa = login("13800000000", "admin123456")
    ensure_fake_platform(pa)
    token = login("13900000099", "test123456")

    cases = [
        ("VA1b-1 你好 → clarify", "你好", False, "clarify"),
        ("VA1b-2 过短「写」→ clarify", "写", False, "clarify"),
        (
            "VA1b-3 明确题材 → proceed 或 clarify",
            "帮我写一篇少儿编程招生小红书笔记",
            None,
            None,
        ),
    ]
    for label, msg, expect_ready, expect_action in cases:
        code, session = req(
            "POST",
            "/agent/sessions",
            token=token,
            body={"title": f"Preflight: {msg[:12]}"},
        )
        sid = session.get("id") if code == 200 else None
        if not sid:
            results.append(check(label, False, "create session failed"))
            continue
        c, pre = preflight(token, sid, msg)
        ok = c == 200
        if expect_ready is not None:
            ok = ok and pre.get("ready") is expect_ready
        if expect_action:
            ok = ok and pre.get("action") == expect_action
        elif msg.startswith("帮我写"):
            ok = ok and pre.get("action") in ("proceed", "clarify", "chat")
        results.append(check(label, ok, str(pre)[:200]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", default="1b-clarify")
    args = parser.parse_args()

    results: list[bool] = []
    step_1b_clarify(results)

    passed = sum(results)
    total = len(results)
    print(f"\n=== verify_advisor_1b: {passed}/{total} PASS ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
