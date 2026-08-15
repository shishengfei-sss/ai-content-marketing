#!/usr/bin/env python3
"""商城权限 M0 验收：Catalog + 内置角色种子 + API 权限门控。"""

from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req, req_upload  # noqa: E402


def login(phone: str, password: str, workspace_mode: str | None = None) -> str:
    body: dict = {"phone": phone, "password": password}
    if workspace_mode:
        body["workspace_mode"] = workspace_mode
    code, data = req("POST", "/auth/login", body=body)
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []

    from app.permissions import (  # noqa: E402
        ALL_PERMISSIONS,
        PLATFORM_SHOP_CS_DEFAULT_PERMISSIONS,
        PLATFORM_SHOP_OPS_DEFAULT_PERMISSIONS,
        PLATFORM_SHOP_PERMISSIONS,
        SHOP_BUILTIN_ROLE_CODES,
        SHOP_BUILTIN_ROLE_DEFAULT_PERMISSIONS,
        SHOP_MERCHANT_PERMISSIONS,
    )

    results.append(check("VS-1 shop权限数量", len(SHOP_MERCHANT_PERMISSIONS) == 37, str(len(SHOP_MERCHANT_PERMISSIONS))))
    results.append(
        check(
            "VS-2 platform.shop数量",
            len(PLATFORM_SHOP_PERMISSIONS) == 19,
            str(len(PLATFORM_SHOP_PERMISSIONS)),
        )
    )
    results.append(
        check(
            "VS-3 ALL含shop不含platform",
            all(p in ALL_PERMISSIONS for p in SHOP_MERCHANT_PERMISSIONS)
            and all(p not in ALL_PERMISSIONS for p in PLATFORM_SHOP_PERMISSIONS),
            "",
        )
    )
    results.append(
        check(
            "VS-4 内置角色数",
            len(SHOP_BUILTIN_ROLE_CODES) == 4,
            ",".join(sorted(SHOP_BUILTIN_ROLE_CODES)),
        )
    )
    results.append(
        check(
            "VS-5 管家无subscription.manage",
            "platform.shop.subscription.manage" not in PLATFORM_SHOP_CS_DEFAULT_PERMISSIONS,
            "",
        )
    )
    results.append(
        check(
            "VS-5b 运营无onboarding.initiate",
            "platform.shop.onboarding.initiate" not in PLATFORM_SHOP_OPS_DEFAULT_PERMISSIONS,
            "",
        )
    )
    results.append(
        check(
            "VS-5c 管家有onboarding.initiate",
            "platform.shop.onboarding.initiate" in PLATFORM_SHOP_CS_DEFAULT_PERMISSIONS,
            "",
        )
    )
    results.append(
        check(
            "VS-5d 管家/运营有merchant.tag",
            "platform.shop.merchant.tag" in PLATFORM_SHOP_CS_DEFAULT_PERMISSIONS
            and "platform.shop.merchant.tag" in PLATFORM_SHOP_OPS_DEFAULT_PERMISSIONS,
            "",
        )
    )
    results.append(
        check(
            "VS-5e 仅运营可新建标签名",
            "platform.shop.merchant.tag.manage" not in PLATFORM_SHOP_CS_DEFAULT_PERMISSIONS
            and "platform.shop.merchant.tag.manage" in PLATFORM_SHOP_OPS_DEFAULT_PERMISSIONS,
            "",
        )
    )
    results.append(
        check(
            "VS-6 店员仅核销",
            SHOP_BUILTIN_ROLE_DEFAULT_PERMISSIONS["shop_clerk"]
            == {"shop.redemption.execute", "shop.redemption.list_own", "shop.redemption.read"},
            "",
        )
    )

    from tests.shop_catalog_helper import ensure_demo_merchant_admin  # noqa: E402

    ensure_demo_merchant_admin("13900000099")
    token = login("13900000099", "test123456", "merchant")
    code, me = req("GET", "/auth/me", token=token)
    results.append(check("VS-7 租户me含shop权限", code == 200 and any(p.startswith("shop.") for p in me.get("permissions", [])), str(me.get("permissions", [])[:5])))

    code, catalog = req("GET", "/shop/permissions/catalog", token=token)
    results.append(check("VS-8 商家catalog", code == 200 and len(catalog.get("permissions", [])) == 37, str(code)))

    code, roles = req("GET", "/shop/roles", token=token)
    role_rows = roles if isinstance(roles, list) else (roles or {}).get("items") or []
    role_codes = {r.get("code") for r in role_rows if isinstance(r, dict)}
    results.append(
        check(
            "VS-9 商家角色列表",
            code == 200
            and {"shop_admin", "shop_content", "shop_support", "shop_clerk"} <= role_codes,
            str(sorted(role_codes) if role_codes else code),
        )
    )

    admin_token = login("13800000000", "admin123456")
    code, pme = req("GET", "/auth/me", token=admin_token)
    results.append(
        check(
            "VS-10 平台me含platform_shop",
            code == 200 and len(pme.get("platform_shop_permissions", [])) == 19,
            str(len(pme.get("platform_shop_permissions", []))),
        )
    )

    code, pcatalog = req("GET", "/admin/shop/permissions/catalog", token=admin_token)
    results.append(check("VS-11 平台catalog", code == 200 and len(pcatalog.get("permissions", [])) == 19, str(code)))

    code, merchants = req("GET", "/admin/shop/merchants", token=admin_token)
    results.append(
        check(
            "VS-12 平台商家列表",
            code == 200 and merchants.get("scope") == "all" and merchants.get("total", 0) >= 1,
            str(merchants.get("total")),
        )
    )

    code, renewals = req("GET", "/admin/shop/merchants/pending-renewals", token=admin_token)
    results.append(
        check(
            "VS-13 续费待办",
            code == 200 and renewals.get("total", 0) >= 0,
            str(renewals.get("total")),
        )
    )

    code, tenant_opts = req("GET", "/admin/shop/onboarding/tenant-options", token=admin_token)
    results.append(
        check(
            "VS-14 入驻租户候选",
            code == 200 and isinstance(tenant_opts.get("items"), list),
            str(tenant_opts.get("total")),
        )
    )

    target_tenant_id = None
    created_app_id = None
    if tenant_opts.get("items"):
        target_tenant_id = tenant_opts["items"][0]["tenant_id"]

    if target_tenant_id:
        code, prefill = req("GET", f"/admin/shop/onboarding/tenants/{target_tenant_id}/prefill", token=admin_token)
        results.append(
            check(
                "VS-15 入驻预填",
                code == 200 and prefill.get("tenant_id") == target_tenant_id,
                str(code),
            )
        )
        code, created = req(
            "POST",
            "/admin/shop/onboarding/applications",
            token=admin_token,
            body={
                "tenant_id": target_tenant_id,
                "entity_type": "enterprise",
                "legal_name": prefill.get("legal_name", "测试主体"),
                "display_name": prefill.get("display_name", "测试商家"),
                "contact_name": "测试联系人",
                "contact_mobile": "13900001111",
                "unified_social_credit_code": "91110000MA01234567",
                "legal_rep_name": "张三",
                "qualification_files": {},
                "ocr_results": [],
                "remark": "验收脚本发起",
            },
        )
        results.append(
            check(
                "VS-16 发起入驻",
                code == 201 and created.get("status") == "pending",
                str(code),
            )
        )
        created_app_id = created.get("id")
        code, dup = req(
            "POST",
            "/admin/shop/onboarding/applications",
            token=admin_token,
            body={
                "tenant_id": target_tenant_id,
                "entity_type": "enterprise",
                "legal_name": "重复",
                "contact_name": "测试",
                "contact_mobile": "13900001111",
                "unified_social_credit_code": "91110000MA01234567",
                "legal_rep_name": "张三",
            },
        )
        results.append(check("VS-17 重复入驻409", code == 409, str(code)))

        code, reviewing = req("GET", f"/admin/shop/merchants/{target_tenant_id}", token=admin_token)
        results.append(
            check(
                "VS-18 审核中详情",
                code == 200 and reviewing.get("onboarding_status") == "reviewing",
                str(reviewing.get("onboarding_status")),
            )
        )
    else:
        results.append(check("VS-15 入驻预填", False, "无可用租户"))
        results.append(check("VS-16 发起入驻", False, "跳过"))
        results.append(check("VS-17 重复入驻409", False, "跳过"))
        results.append(check("VS-18 审核中详情", False, "跳过"))

    code, merchants2 = req("GET", "/admin/shop/merchants", token=admin_token)
    detail_tid = None
    if merchants2.get("items"):
        for item in merchants2["items"]:
            if item.get("merchant_id"):
                detail_tid = item["tenant_id"]
                break
    if detail_tid:
        code, detail = req("GET", f"/admin/shop/merchants/{detail_tid}", token=admin_token)
        results.append(
            check(
                "VS-19 已入驻详情",
                code == 200
                and detail.get("merchant_id")
                and detail.get("onboarding_status") in ("active", "suspended", "closed"),
                str(detail.get("onboarding_status")),
            )
        )
        results.append(
            check(
                "VS-20 详情含店铺",
                isinstance(detail.get("stores"), list),
                str(len(detail.get("stores", []))),
            )
        )
    else:
        results.append(check("VS-19 已入驻详情", False, "无商家"))
        results.append(check("VS-20 详情含店铺", False, "跳过"))

    code, app_list = req("GET", "/admin/shop/onboarding/applications?status=pending", token=admin_token)
    results.append(
        check(
            "VS-21 P03待审列表",
            code == 200 and app_list.get("total", 0) >= 1,
            str(app_list.get("total")),
        )
    )

    ocr_tid = target_tenant_id or detail_tid
    if ocr_tid:
        up_code, up = req_upload(
            "/admin/shop/onboarding/files",
            admin_token,
            {"tenant_id": str(ocr_tid), "doc_type": "business_license"},
        )
        fid = up.get("file_id") if isinstance(up, dict) else None
        code, ocr = req(
            "POST",
            "/admin/shop/onboarding/ocr",
            token=admin_token,
            body={"doc_type": "business_license", "file_id": fid, "tenant_id": ocr_tid},
        )
        results.append(
            check(
                "VS-22 平台OCR stub",
                up_code == 201
                and bool(fid)
                and code == 200
                and ocr.get("stub") is True
                and "unified_social_credit_code" in ocr.get("fields", {}),
                str(code),
            )
        )
    else:
        results.append(check("VS-22 平台OCR stub", False, "无租户"))

    if created_app_id:
        code, approved = req(
            "POST",
            f"/admin/shop/onboarding/applications/{created_app_id}/approve",
            token=admin_token,
            body={"plan_label": "7天试用基础版", "trial_days": 7, "store_quota": 1},
        )
        results.append(
            check(
                "VS-23 P03审核通过",
                code == 200 and approved.get("merchant_id") is not None,
                str(code),
            )
        )
    else:
        results.append(check("VS-23 P03审核通过", False, "无待审单"))

    mup_code, mup = req_upload(
        "/shop/onboarding/files",
        token,
        {"doc_type": "id_card_front"},
    )
    mfid = mup.get("file_id") if isinstance(mup, dict) else None
    code, mocr = req(
        "POST",
        "/shop/onboarding/ocr",
        token=token,
        body={"doc_type": "id_card_front", "file_id": mfid},
    )
    results.append(
        check(
            "VS-24 商家OCR stub",
            mup_code == 201
            and bool(mfid)
            and code == 200
            and mocr.get("stub") is True
            and "id_no" in mocr.get("fields", {}),
            str(code),
        )
    )

    expiring_tid = None
    if merchants2.get("items"):
        for item in merchants2["items"]:
            if (
                item.get("merchant_id")
                and item.get("plan_status") in ("expiring_soon", "expired")
                and not item.get("has_pending_renewal")
            ):
                expiring_tid = item["tenant_id"]
                break
    if expiring_tid:
        code, renewal = req(
            "POST",
            f"/admin/shop/merchants/{expiring_tid}/service-logs/renewal-requests",
            token=admin_token,
            body={
                "purchase_mode": "renew_same",
                "target_plan": "旗舰版（1年）",
                "quoted_amount_cents": 980000,
                "catalog_price_cents": 980000,
                "customer_confirmed": True,
                "content": "客户已确认续费，请运营本周内开通",
            },
        )
        results.append(
            check(
                "VS-25 续费申请",
                code in (201, 409)
                and (code == 409 or (renewal.get("type") == "renewal_request" and renewal.get("status") == "pending")),
                str(code),
            )
        )
    else:
        results.append(check("VS-25 续费申请", False, "无即将到期商家"))

    if detail_tid:
        code, note = req(
            "POST",
            f"/admin/shop/merchants/{detail_tid}/service-logs/notes",
            token=admin_token,
            body={"type": "note", "content": "验收脚本写入跟进备注，确认客户意向良好"},
        )
        results.append(
            check(
                "VS-26 服务跟进备注",
                code == 201 and note.get("type") == "note",
                str(code),
            )
        )
    else:
        results.append(check("VS-26 服务跟进备注", False, "跳过"))

    ok = all(results)
    print(f"\n{'PASS' if ok else 'FAIL'} {sum(1 for r in results if r)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
