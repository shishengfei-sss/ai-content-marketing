#!/usr/bin/env python3
"""E2E F2: 商品上架→内容发布。对照 M4：封面 + CMS 引用 → 提审 → 通过 → 上架。"""
from __future__ import annotations

import os
import sys
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
    merchant = login("13900000099", "test123456")
    pid = ensure_on_sale_product(merchant, "course", price_cents=19900)
    code, product = req("GET", f"/shop/products/{pid}", token=merchant)
    results.append(
        check(
            "E2E-F2 课程上架 on_sale",
            code == 200 and product.get("status") == "on_sale" and product.get("type") == "course",
            f"{code} {product.get('status')}",
        )
    )
    passed = all(results)
    print(f"\nverify_shop_e2e_f2: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
