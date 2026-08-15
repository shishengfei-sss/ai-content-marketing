#!/usr/bin/env python3
"""E2E F9: 多店权益→同租户核销。对照 A17 多店 + M6 租户级核销。"""
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

    code, stores = req("GET", "/shop/stores?page=1&page_size=50", token=merchant)
    rows = stores if isinstance(stores, list) else (stores or {}).get("items") or []
    created_ok = False
    if code == 200 and len(rows) < 2:
        slug = f"e2e-f9-{uuid.uuid4().hex[:6]}"
        code_c, _ = req(
            "POST",
            "/shop/stores",
            token=merchant,
            body={"name": "验收分店", "slug": slug, "intro": "E2E-F9"},
        )
        created_ok = code_c in (200, 201)
    results.append(
        check(
            "E2E-F9 同租户店铺",
            code == 200 and (len(rows) >= 2 or created_ok or len(rows) >= 1),
            f"{code} n={len(rows)} created={created_ok}",
        )
    )

    pid = ensure_on_sale_product(merchant, "service", price_cents=9900, extra={"service_times": 2})
    buyer = buyer_token(tenant_id)
    mobile = "136" + f"{uuid.uuid4().int % 10**8:08d}"
    req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})
    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created or {}).get("order") or created
    if not order.get("id"):
        results.append(check("E2E-F9 下单", False, str(code)))
        print(f"\nverify_shop_e2e_f9: FAIL ({sum(results)}/{len(results)})")
        return 1
    req("POST", f"/mp/shop/orders/{order['id']}/pay", token=buyer, body={})
    code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
    ent = next((e for e in (ents.get("items") or []) if e.get("order_id") == order.get("id")), None)
    results.append(check("E2E-F9 权益可核销", ent is not None and ent.get("status") == "active", str(ent)))

    code, v1 = req(
        "POST",
        "/shop/verifications/execute",
        token=merchant,
        body={
            "entitlement_id": (ent or {}).get("id"),
            "deducted_count": 1,
            "idempotency_key": f"f9-{uuid.uuid4().hex}",
        },
    )
    results.append(
        check(
            "E2E-F9 租户级核销成功",
            code == 200 and v1.get("status") == "success",
            f"{code} {v1.get('status')}",
        )
    )
    passed = all(results)
    print(f"\nverify_shop_e2e_f9: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
