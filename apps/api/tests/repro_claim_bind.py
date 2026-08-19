#!/usr/bin/env python3
"""领权页完整演示链路：模拟下单 → 授权（不 bind）→ 确认领取。"""
from __future__ import annotations

import os
import sys
import uuid

os.environ["VERIFY_LIVE_API"] = "1"
os.environ.setdefault("VERIFY_API_BASE", "http://127.0.0.1:8003/api/v1")
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.http_client import req  # noqa: E402

TENANT = "61311884-14e0-45c2-96b3-2d028e97bd01"
MAPPING_ID = "1594de00-f0a8-467d-bfc1-75a973312359"
MOBILE = "13700000001"
MERCHANT_PHONE = "13434777599"
MERCHANT_PASSWORD = os.environ.get("SHOP_DEMO_PASSWORD", "test123456")


def login_merchant() -> str:
    for pwd in (MERCHANT_PASSWORD, "admin123456", "12345678"):
        code, data = req("POST", "/auth/login", body={"phone": MERCHANT_PHONE, "password": pwd})
        if code == 200 and data.get("access_token"):
            return data["access_token"]
    raise RuntimeError(f"cannot login merchant {MERCHANT_PHONE}")


def main() -> None:
    shop_token = login_merchant()
    code, demo = req(
        "POST",
        f"/shop/channel-mappings/{MAPPING_ID}/demo-order",
        token=shop_token,
        body={"buyer_mobile": MOBILE},
    )
    print("demo-order", code, demo)
    if code != 200:
        return

    token = demo.get("claim_token")
    code, info = req("GET", f"/mp/shop/claim/{token}")
    print("GET claim", code, info.get("status"), info.get("mobile_tail"))
    if code != 200 or info.get("status") != "pending":
        print("abort: claim not pending")
        return

    openid = f"claim_{token[:8]}"
    code, login = req(
        "POST",
        "/mp/shop/auth/login",
        body={"tenant_id": TENANT, "code": f"mock:{openid}"},
    )
    buyer_token = (login or {}).get("access_token")
    print("login", code, openid)

    code2, claimed = req("POST", f"/mp/shop/claim/{token}", token=buyer_token)
    print("confirm", code2, claimed)
    if code2 != 200 or claimed.get("status") != "claimed":
        raise SystemExit(1)

    code3, me = req("GET", "/mp/shop/auth/me", token=buyer_token)
    print("me", code3, me)
    if code3 != 200 or me.get("mobile") != MOBILE:
        raise SystemExit(1)
    print("OK: claim demo flow passed")


if __name__ == "__main__":
    main()
