#!/usr/bin/env python3
"""E2E F1: 套餐订阅→权益开通。对照 M1 / P10 / P11。"""
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
    raise RuntimeError("no active merchant for F1")


def main() -> int:
    results: list[bool] = []
    admin = login("13800000000", "admin123456")
    tenant_id = _pick_active_tenant(admin)

    code, plans = req("GET", "/admin/shop/plan-templates?published=true", token=admin)
    results.append(
        check(
            "E2E-F1 套餐模板可购",
            code == 200 and (plans or {}).get("total", 0) >= 3,
            str(code),
        )
    )

    today = date.today()
    expires = today + timedelta(days=365) - timedelta(days=1)
    code, sub = req(
        "POST",
        "/admin/shop/subscriptions",
        token=admin,
        body={
            "tenant_id": tenant_id,
            "plan_code": "basic",
            "purchase_mode": "replace",
            "effective_at": today.isoformat(),
            "expires_at": expires.isoformat(),
            "catalog_price_cents": 980000,
            "paid_amount_cents": 980000,
            "source": "manual",
            "remark": "E2E-F1 验收开通",
        },
    )
    results.append(
        check(
            "E2E-F1 人工开通 basic",
            code == 200 and sub.get("status") == "active" and sub.get("plan_code") == "basic",
            f"{code} {sub.get('status')}",
        )
    )

    code, ent = req("GET", f"/admin/shop/merchants/{tenant_id}/entitlements", token=admin)
    quotas = (ent or {}).get("quotas") or {}
    results.append(
        check(
            "E2E-F1 店铺额度生效",
            code == 200 and int(quotas.get("quota.max_products") or 0) >= 200,
            f"{code} products={quotas.get('quota.max_products')}",
        )
    )
    passed = all(results)
    print(f"\nverify_shop_e2e_f1: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
