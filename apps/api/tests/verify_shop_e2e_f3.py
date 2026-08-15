#!/usr/bin/env python3
"""E2E F3: 买家下单→待支付。对照 M04 / M5 创建订单。"""
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
from tests.shop_catalog_helper import ensure_on_sale_product  # noqa: E402


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []
    from tests.shop_catalog_helper import ensure_demo_merchant_admin, resolve_tenant_id  # noqa: E402

    ensure_demo_merchant_admin()
    merchant = login("13900000099", "test123456")
    tenant_id = resolve_tenant_id(merchant)
    pid = ensure_on_sale_product(merchant, "course", price_cents=19900)

    openid = f"e2e_f3_{uuid.uuid4().hex[:8]}"
    code, buyer_data = req(
        "POST", "/mp/shop/auth/login", body={"tenant_id": tenant_id, "code": f"mock:{openid}"}
    )
    results.append(check("E2E-F3 买家登录", code == 200, str(code)))
    buyer = buyer_data.get("access_token")
    mobile = "136" + f"{uuid.uuid4().int % 10**8:08d}"
    code, _ = req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})
    results.append(check("E2E-F3 绑定手机", code == 200, str(code)))

    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created or {}).get("order") or created
    results.append(
        check(
            "E2E-F3 下单 pending_payment",
            code == 200 and order.get("status") == "pending_payment",
            f"{code} {order.get('status') or created}",
        )
    )
    passed = all(results)
    print(f"\nverify_shop_e2e_f3: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
