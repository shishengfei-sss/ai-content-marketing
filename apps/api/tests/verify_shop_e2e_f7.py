#!/usr/bin/env python3
"""E2E F7: 商家暂停→已购不阻断。对照 M2 暂停/恢复 + M02 店首页闸。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

from tests.http_client import check, req  # noqa: E402


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []

    token = login("13800000000", "admin123456")

    # ── F7-1: 商家列表 ──
    code, merchants = req("GET", "/admin/shop/merchants", token=token)
    results.append(
        check(
            "E2E-F7-1 商家列表",
            code == 200 and merchants.get("total", 0) >= 1,
            str(merchants.get("total")),
        )
    )

    # ── F7-2: 商家详情含 onboarding_status ──
    detail_tid = None
    if code == 200 and merchants.get("items"):
        for item in merchants["items"]:
            if item.get("merchant_id"):
                detail_tid = item["tenant_id"]
                break
    if detail_tid:
        code, detail = req(
            "GET",
            f"/admin/shop/merchants/{detail_tid}",
            token=token,
        )
        results.append(
            check(
                "E2E-F7-2 商家详情含状态",
                code == 200
                and detail.get("onboarding_status") in ("active", "suspended", "closed"),
                str(detail.get("onboarding_status")),
            )
        )
    else:
        results.append(check("E2E-F7-2 商家详情含状态", False, "无已入驻商家"))

    # ── F7-3/4: 暂停店首页拦截，已购权益仍可读；结束必须恢复 ──
    from tests.shop_catalog_helper import (  # noqa: E402
        buyer_token,
        ensure_demo_merchant_admin,
        ensure_on_sale_product,
        resolve_tenant_id,
    )

    ensure_demo_merchant_admin()
    merchant = login("13900000099", "test123456")
    tenant_id = resolve_tenant_id(merchant)
    code, stores = req("GET", "/shop/stores", token=merchant)
    rows = stores if isinstance(stores, list) else (stores or {}).get("items") or []
    shop_id = str(rows[0]["id"]) if rows else None

    buyer = buyer_token(str(tenant_id), f"e2e_f7_{os.urandom(3).hex()}") if tenant_id else None
    if buyer and shop_id:
        pid = ensure_on_sale_product(merchant, "course", price_cents=9900)
        code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
        order = (created or {}).get("order") or created
        if order.get("id"):
            req("POST", f"/mp/shop/orders/{order['id']}/pay", token=buyer, body={})
        try:
            code, d1 = req(
                "POST",
                f"/admin/shop/merchants/{tenant_id}/suspend",
                token=token,
                body={"reason_code": "other", "reason_text": "E2E-F7 验收暂停原因足够"},
            )
            results.append(
                check(
                    "E2E-F7-3 商家暂停",
                    code == 200 and d1.get("onboarding_status") == "suspended",
                    f"{code} {d1.get('onboarding_status')}",
                )
            )
            code, store = req("GET", f"/mp/shop/store?shop_id={shop_id}")
            results.append(
                check(
                    "E2E-F7-3b 暂停后门店 403",
                    code == 403,
                    str(code),
                )
            )
            code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
            results.append(
                check(
                    "E2E-F7-4 已购权益不阻断",
                    code == 200 and isinstance((ents or {}).get("items"), list),
                    str(code),
                )
            )
        finally:
            req(
                "POST",
                f"/admin/shop/merchants/{tenant_id}/resume",
                token=token,
                body={"note": "E2E-F7 验收恢复"},
            )
    else:
        results.append(check("E2E-F7-3 商家暂停", False, "无店铺或买家"))
        results.append(check("E2E-F7-4 已购权益不阻断", False, "无店铺或买家"))

    passed = sum(results)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
