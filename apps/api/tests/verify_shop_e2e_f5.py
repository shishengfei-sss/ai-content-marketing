#!/usr/bin/env python3
"""E2E F5: 核销码生成→店员核销。对照 M6。"""
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
    pid = ensure_on_sale_product(merchant, "service", price_cents=9900, extra={"service_times": 2})

    buyer = buyer_token(tenant_id)
    mobile = "136" + f"{uuid.uuid4().int % 10**8:08d}"
    req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})

    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created or {}).get("order") or created
    results.append(check("E2E-F5 下单", code == 200 and bool(order.get("id")), str(code)))
    if not order.get("id"):
        print(f"\nverify_shop_e2e_f5: FAIL ({sum(results)}/{len(results)})")
        return 1

    code, paid = req("POST", f"/mp/shop/orders/{order['id']}/pay", token=buyer, body={})
    results.append(check("E2E-F5 Mock 支付", code == 200, str(code)))

    code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
    ent = next((e for e in (ents.get("items") or []) if e.get("order_id") == order.get("id")), None)
    vc = (ent or {}).get("verify_code") or ""
    results.append(
        check(
            "E2E-F5 核销码生成",
            ent is not None and isinstance(vc, str) and len(vc) == 6 and vc.isdigit(),
            f"{code} {vc}",
        )
    )

    code, look = req("POST", "/shop/verifications/lookup", token=merchant, body={"verify_code": vc})
    results.append(
        check(
            "E2E-F5 lookup 可核销",
            code == 200 and look.get("result") in ("can_redeem", "multi"),
            f"{code} {look.get('result')}",
        )
    )

    code, v1 = req(
        "POST",
        "/shop/verifications/execute",
        token=merchant,
        body={"entitlement_id": (ent or {}).get("id"), "deducted_count": 1, "idempotency_key": f"f5-{uuid.uuid4().hex}"},
    )
    results.append(
        check(
            "E2E-F5 核销扣次",
            code == 200 and v1.get("status") == "success",
            f"{code} {v1.get('status')}",
        )
    )
    passed = all(results)
    print(f"\nverify_shop_e2e_f5: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
