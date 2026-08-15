#!/usr/bin/env python3
"""E2E F11: 开票申请→电子发票。对照 M6 开票。"""
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
        results.append(check("E2E-F11 下单", False, str(code)))
        print(f"\nverify_shop_e2e_f11: FAIL ({sum(results)}/{len(results)})")
        return 1
    req("POST", f"/mp/shop/orders/{order['id']}/pay", token=buyer, body={})

    code, inv = req(
        "POST",
        "/mp/shop/invoices",
        token=buyer,
        body={
            "order_id": order["id"],
            "title_type": "person",
            "title": "验收开票",
            "email": "f11@example.com",
        },
    )
    results.append(
        check(
            "E2E-F11 买家申请开票",
            code == 200 and bool(inv.get("id")),
            f"{code} {inv.get('status')}",
        )
    )
    inv_id = inv.get("id")
    inv_no = f"F11{uuid.uuid4().hex[:8].upper()}"
    code, issued = req(
        "POST",
        f"/shop/invoices/{inv_id}/issue",
        token=merchant,
        body={"invoice_no": inv_no, "invoice_url": "https://example.com/inv/f11.pdf"},
    )
    results.append(
        check(
            "E2E-F11 商家开具电子发票",
            code == 200 and issued.get("invoice_no") == inv_no,
            f"{code} {issued.get('invoice_no')}",
        )
    )
    passed = all(results)
    print(f"\nverify_shop_e2e_f11: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
