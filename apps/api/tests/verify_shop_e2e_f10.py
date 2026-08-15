#!/usr/bin/env python3
"""E2E F10: 清结算周关账 → P05 列表可见。对照 03#f10 · 06#p05。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

from tests.http_client import check, req  # noqa: E402


def login(phone: str, password: str, workspace_mode: str | None = None) -> str:
    body: dict = {"phone": phone, "password": password}
    if workspace_mode:
        body["workspace_mode"] = workspace_mode
    code, data = req("POST", "/auth/login", body=body)
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []
    admin = login("13800000000", "admin123456", "platform")
    code, closed = req("POST", "/admin/shop/settlement-batches/close-period", token=admin, body={})
    results.append(check("VF10-1 周关账", code == 200 and "created" in (closed or {}), f"{code} {closed}"))
    code, listing = req("GET", "/admin/shop/settlement-batches?page=1&page_size=20", token=admin)
    results.append(
        check(
            "VF10-2 P05 列表",
            code == 200 and isinstance((listing or {}).get("items"), list),
            f"{code}",
        )
    )
    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nF10 result: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
