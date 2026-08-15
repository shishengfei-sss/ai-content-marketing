#!/usr/bin/env python3
"""权限隔离验收：商家间数据隔离、平台权限、店员仅核销、RBAC。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req, req_upload  # noqa: E402


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []

    from tests.shop_catalog_helper import ensure_demo_merchant_admin  # noqa: E402

    ensure_demo_merchant_admin()
    tenant_token = login("13900000099", "test123456")
    admin_token = login("13800000000", "admin123456")

    # ── SEC-1 商家间数据隔离（租户无法访问平台商家列表）──
    code, data = req("GET", "/admin/shop/merchants", token=tenant_token)
    results.append(
        check(
            "SEC-1 商家无法访问平台商家列表(403)",
            code == 403,
            f"code={code}",
        )
    )

    # 租户无法访问平台商家详情（使用任意 UUID）
    code2, _ = req("GET", "/admin/shop/merchants/00000000-0000-0000-0000-000000000001", token=tenant_token)
    results.append(
        check(
            "SEC-1 商家无法访问平台商家详情(403/404)",
            code2 in (403, 404),
            f"code={code2}",
        )
    )

    # ── SEC-2 平台管理员拥有 platform_shop 权限 ──
    code, me = req("GET", "/auth/me", token=admin_token)
    platform_shop_perms = me.get("platform_shop_permissions", []) if isinstance(me, dict) else []
    results.append(
        check(
            "SEC-2 平台管理员含platform_shop权限",
            code == 200 and len(platform_shop_perms) >= 1,
            f"perms_count={len(platform_shop_perms)}",
        )
    )

    # 平台管理员可访问商家列表
    code, merchants = req("GET", "/admin/shop/merchants", token=admin_token)
    results.append(
        check(
            "SEC-2 平台管理员可访问商家列表",
            code == 200 and merchants.get("total", 0) >= 1,
            f"code={code}, total={merchants.get('total') if isinstance(merchants, dict) else 'N/A'}",
        )
    )

    # ── SEC-3 店员仅可核销（验证角色权限定义）──
    from app.permissions import (  # noqa: E402
        SHOP_BUILTIN_ROLE_DEFAULT_PERMISSIONS,
        SHOP_CLERK_DEFAULT_PERMISSIONS,
    )

    clerk_perms = SHOP_BUILTIN_ROLE_DEFAULT_PERMISSIONS.get("shop_clerk", set())
    results.append(
        check(
            "SEC-3 店员仅有核销权限",
            clerk_perms == SHOP_CLERK_DEFAULT_PERMISSIONS
            and "shop.redemption.execute" in clerk_perms
            and "shop.product.manage" not in clerk_perms
            and "shop.order.manage" not in clerk_perms,
            f"perms={sorted(clerk_perms)}",
        )
    )

    # ── SEC-4 RBAC — 商家端角色权限分层 ──
    from app.permissions import (  # noqa: E402
        SHOP_ADMIN_DEFAULT_PERMISSIONS,
        SHOP_CONTENT_DEFAULT_PERMISSIONS,
        SHOP_SUPPORT_DEFAULT_PERMISSIONS,
    )

    # 店员无商品写入权限，管家有
    has_separation = (
        "shop.product.write" not in clerk_perms
        and "shop.product.write" in SHOP_ADMIN_DEFAULT_PERMISSIONS
    )
    # 内容管理员有商品写入但无订单退款
    content_no_order = (
        "shop.product.write" in SHOP_CONTENT_DEFAULT_PERMISSIONS
        and "shop.order.refund" not in SHOP_CONTENT_DEFAULT_PERMISSIONS
    )
    # 客服有订单退款但无商品写入
    support_no_product_write = (
        "shop.product.write" not in SHOP_SUPPORT_DEFAULT_PERMISSIONS
        and "shop.order.refund" in SHOP_SUPPORT_DEFAULT_PERMISSIONS
    )
    results.append(
        check(
            "SEC-4 RBAC角色权限分层",
            has_separation and content_no_order and support_no_product_write,
            f"admin_has_product_write={'shop.product.write' in SHOP_ADMIN_DEFAULT_PERMISSIONS}, "
            f"clerk_no_product_write={'shop.product.write' not in clerk_perms}, "
            f"content_no_order={content_no_order}, support_no_write={support_no_product_write}",
        )
    )

    # 验证租户端 catalog 仅返回 shop 权限（不含 platform.shop）
    code, catalog = req("GET", "/shop/permissions/catalog", token=tenant_token)
    catalog_raw = catalog.get("permissions", []) if isinstance(catalog, dict) else []
    # catalog 返回 [{"code": "shop.xxx", "scope": "merchant"}, ...]
    catalog_codes = [
        item["code"] if isinstance(item, dict) else str(item)
        for item in catalog_raw
    ]
    has_no_platform = all(not p.startswith("platform.") for p in catalog_codes)
    results.append(
        check(
            "SEC-4 租户catalog不含platform权限",
            code == 200 and has_no_platform and len(catalog_codes) > 0,
            f"perms_count={len(catalog_codes)}, has_platform={not has_no_platform}",
        )
    )

    # ── SEC-OCR 入驻材料 file_id 跨租户隔离 ──
    up_code, up = req_upload("/shop/onboarding/files", tenant_token, {"doc_type": "id_card_front"})
    own_fid = up.get("file_id") if isinstance(up, dict) else None
    other_token = None
    try:
        other_token = login("13900000101", "demo123456")
    except AssertionError:
        other_token = None
    if own_fid and other_token:
        code_x, _ = req(
            "POST",
            "/shop/onboarding/ocr",
            token=other_token,
            body={"doc_type": "id_card_front", "file_id": own_fid},
        )
        results.append(
            check(
                "SEC-OCR 跨租户 file_id 拒绝",
                code_x in (403, 404),
                f"code={code_x}",
            )
        )
    else:
        results.append(check("SEC-OCR 跨租户 file_id 拒绝", False, "无 file_id 或审核中商家账号"))
    code_ok, _ = req(
        "POST",
        "/shop/onboarding/ocr",
        token=tenant_token,
        body={"doc_type": "id_card_front", "file_id": own_fid},
    )
    results.append(
        check(
            "SEC-OCR 本租户 file_id 可识别",
            up_code == 201 and bool(own_fid) and code_ok == 200,
            f"up={up_code} ocr={code_ok}",
        )
    )

    code, me = req("GET", "/auth/me", token=tenant_token)
    at = (me or {}).get("active_tenant") if isinstance(me, dict) else None
    tid = at.get("id") if isinstance(at, dict) else None
    if not tid and isinstance(me, dict):
        tenants = me.get("tenants") or []
        tid = tenants[0].get("id") if tenants else None
    if tid:
        from tests.verify_shop_m6 import _ensure_clerk_token

        clerk = _ensure_clerk_token(str(tid))
        code_c, data_c = req(
            "POST",
            "/shop/onboarding/ocr",
            token=clerk,
            body={"doc_type": "id_card_front", "file_id": own_fid or "00000000-0000-0000-0000-000000000001"},
        )
        results.append(
            check(
                "SEC-A20 店员不可刷入驻识别",
                code_c == 403,
                f"code={code_c} {data_c}",
            )
        )
        code_st, _ = req("GET", "/shop/onboarding/status", token=clerk)
        results.append(
            check("SEC-A20 店员可读入驻status", code_st == 200, f"code={code_st}")
        )
    else:
        results.append(check("SEC-A20 店员不可刷入驻识别", False, "无 tenant_id"))
        results.append(check("SEC-A20 店员可读入驻status", False, "无 tenant_id"))

    passed = sum(results)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
