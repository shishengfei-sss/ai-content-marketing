#!/usr/bin/env python3
"""E2E F4: Mock 支付→权益激活。对照 M05 / M3 stub 续付。"""
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

    openid = f"e2e_f4_{uuid.uuid4().hex[:8]}"
    code, buyer_data = req(
        "POST", "/mp/shop/auth/login", body={"tenant_id": tenant_id, "code": f"mock:{openid}"}
    )
    buyer = buyer_data.get("access_token")
    mobile = "136" + f"{uuid.uuid4().int % 10**8:08d}"
    req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})

    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created or {}).get("order") or created
    results.append(
        check(
            "E2E-F4 下单",
            code == 200 and bool(order.get("id")),
            f"{code} {order.get('status')}",
        )
    )

    if not order.get("id"):
        results.append(check("E2E-F4 Mock 支付 paid", False, "无订单"))
        results.append(check("E2E-F4 权益激活", False, "无订单"))
        passed = all(results)
        print(f"\nverify_shop_e2e_f4: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)})")
        return 0 if passed else 1

    code, paid = req("POST", f"/mp/shop/orders/{order['id']}/pay", token=buyer, body={})
    paid_order = (paid or {}).get("order") or paid
    results.append(
        check(
            "E2E-F4 Mock 支付 paid",
            code == 200 and paid_order.get("status") == "paid",
            f"{code} {paid_order.get('status')}",
        )
    )

    code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
    ent = next(
        (e for e in (ents.get("items") or []) if e.get("order_id") == order.get("id")),
        None,
    )
    results.append(
        check(
            "E2E-F4 权益激活",
            code == 200 and ent is not None and ent.get("status") == "active",
            f"{code} {ent.get('status') if ent else None}",
        )
    )
    passed = all(results)
    print(f"\nverify_shop_e2e_f4: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
