#!/usr/bin/env python3
"""E2E F6: 退款→权益撤销。对照 M5。"""
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
from tests.shop_catalog_helper import (  # noqa: E402
    buyer_token,
    ensure_demo_merchant_admin,
    ensure_on_sale_product,
    resolve_tenant_id,
)


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []
    ensure_demo_merchant_admin()
    merchant = login("13900000099", "test123456")
    tenant_id = resolve_tenant_id(merchant)
    pid = ensure_on_sale_product(merchant, "course", price_cents=19900)

    buyer = buyer_token(tenant_id)
    mobile = "136" + f"{uuid.uuid4().int % 10**8:08d}"
    req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})

    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created or {}).get("order") or created
    if not order.get("id"):
        results.append(check("E2E-F6 下单", False, str(code)))
        print(f"\nverify_shop_e2e_f6: FAIL ({sum(results)}/{len(results)})")
        return 1
    req("POST", f"/mp/shop/orders/{order['id']}/pay", token=buyer, body={})

    code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
    ent = next((e for e in (ents.get("items") or []) if e.get("order_id") == order.get("id")), None)
    results.append(check("E2E-F6 权益激活", ent is not None and ent.get("status") == "active", str(ent)))

    code, ref = req(
        "POST",
        f"/shop/orders/{order['id']}/refund",
        token=merchant,
        body={"reason": "E2E-F6 全额退"},
    )
    results.append(
        check(
            "E2E-F6 全额退款",
            code == 200 and ref.get("status") == "succeeded",
            f"{code} {ref.get('status')}",
        )
    )

    code, ents2 = req("GET", "/mp/shop/entitlements", token=buyer)
    e2 = next((e for e in (ents2.get("items") or []) if e.get("id") == (ent or {}).get("id")), None)
    results.append(
        check(
            "E2E-F6 权益撤销",
            e2 is not None and e2.get("status") == "revoked",
            f"{code} {e2.get('status') if e2 else None}",
        )
    )
    passed = all(results)
    print(f"\nverify_shop_e2e_f6: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
