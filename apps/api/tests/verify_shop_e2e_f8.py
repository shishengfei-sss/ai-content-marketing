#!/usr/bin/env python3
"""E2E F8: 套餐叠加→权益合并。对照 M1 加购 stack。"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
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


def _pick_active_tenant(admin: str) -> str:
    code, data = req("GET", "/admin/shop/merchants", token=admin)
    assert code == 200, data
    preferred = None
    for item in data.get("items") or []:
        if not item.get("merchant_id") or item.get("onboarding_status") != "active":
            continue
        if item.get("entity_type") in ("enterprise", "individual_business"):
            return item["tenant_id"]
        preferred = preferred or item["tenant_id"]
    if preferred:
        return preferred
    raise RuntimeError("no active merchant for F8")


def main() -> int:
    results: list[bool] = []
    admin = login("13800000000", "admin123456")
    tenant_id = _pick_active_tenant(admin)

    code, before = req("GET", f"/admin/shop/merchants/{tenant_id}/entitlements", token=admin)
    q0 = int(((before or {}).get("quotas") or {}).get("quota.max_products") or 0)
    results.append(check("E2E-F8 叠加前额度可读", code == 200, str(code)))

    today = date.today()
    expires = today + timedelta(days=365) - timedelta(days=1)
    code, addon = req(
        "POST",
        "/admin/shop/subscriptions",
        token=admin,
        body={
            "tenant_id": tenant_id,
            "plan_code": "addon_products_20",
            "purchase_mode": "stack",
            "effective_at": today.isoformat(),
            "expires_at": expires.isoformat(),
            "catalog_price_cents": 59900,
            "paid_amount_cents": 59900,
            "source": "addon",
            "remark": "E2E-F8 加购",
        },
    )
    results.append(
        check(
            "E2E-F8 加购成功",
            code == 200 and addon.get("status") == "active",
            f"{code} {addon.get('status')}",
        )
    )

    code, after = req("GET", f"/admin/shop/merchants/{tenant_id}/entitlements", token=admin)
    q1 = int(((after or {}).get("quotas") or {}).get("quota.max_products") or 0)
    results.append(
        check(
            "E2E-F8 额度合并累加",
            code == 200 and q1 >= q0 + 20,
            f"before={q0} after={q1}",
        )
    )
    passed = all(results)
    print(f"\nverify_shop_e2e_f8: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
