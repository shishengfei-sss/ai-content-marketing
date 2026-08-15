#!/usr/bin/env python3
"""E2E F12: 公域 Mx Mock 闭环。对照 M7 对接配置 + 映射。"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

from tests.http_client import check, req  # noqa: E402
from tests.shop_catalog_helper import ensure_demo_merchant_admin, ensure_on_sale_product  # noqa: E402


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []
    ensure_demo_merchant_admin()
    merchant = login("13900000099", "test123456")
    secret = f"f12_{uuid.uuid4().hex[:12]}"
    dy_shop = f"dy_{uuid.uuid4().hex[:8]}"

    code, cfg = req(
        "POST",
        "/shop/channel-settings",
        token=merchant,
        body={
            "enabled_combos": ["1A"],
            "douyin_shop_id": dy_shop,
            "douyin_webhook_secret": secret,
        },
    )
    results.append(
        check(
            "E2E-F12 对接配置",
            code == 200 and cfg.get("douyin_configured") is True,
            f"{code} {cfg.get('douyin_configured')}",
        )
    )

    pid = ensure_on_sale_product(merchant, "course", price_cents=19900)
    ch_pid = f"dyprod_{uuid.uuid4().hex[:8]}"
    code, mapping = req(
        "POST",
        "/shop/channel-mappings",
        token=merchant,
        body={
            "product_id": pid,
            "channel": "douyin",
            "channel_product_id": ch_pid,
            "combo": "1A",
        },
    )
    results.append(
        check(
            "E2E-F12 抖店映射挂载",
            code == 200 and mapping.get("status") == "mapped",
            f"{code} {mapping.get('status') or mapping}",
        )
    )
    passed = all(results)
    print(f"\nverify_shop_e2e_f12: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
