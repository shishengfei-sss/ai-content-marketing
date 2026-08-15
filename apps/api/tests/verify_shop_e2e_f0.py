#!/usr/bin/env python3
"""E2E F0: 入驻→审核→开店全流程。

平台管理员搜索租户 → 预填 → OCR → 提交入驻申请 → 重复拦截 →
审核中状态 → 待审列表 → 审核通过 → 商家账号创建 → 商家详情验证。

M0 onboarding 已实现，可端到端验收。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

from tests.http_client import check, req, req_upload  # noqa: E402


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []

    # ── 登录平台管理员 ──
    token = login("13800000000", "admin123456")

    # ── F0-1: 搜索入驻租户候选 ──
    code, tenant_opts = req("GET", "/admin/shop/onboarding/tenant-options", token=token)
    results.append(
        check(
            "E2E-F0-1 搜索入驻租户候选",
            code == 200 and isinstance(tenant_opts.get("items"), list),
            str(code),
        )
    )

    target_tenant_id = None
    if code == 200 and tenant_opts.get("items"):
        target_tenant_id = tenant_opts["items"][0]["tenant_id"]

    if target_tenant_id:
        # ── F0-2: 入驻预填 ──
        code, prefill = req(
            "GET",
            f"/admin/shop/onboarding/tenants/{target_tenant_id}/prefill",
            token=token,
        )
        results.append(
            check(
                "E2E-F0-2 入驻预填",
                code == 200 and str(prefill.get("tenant_id")) == str(target_tenant_id),
                str(code),
            )
        )

        # ── F0-3: OCR 证件识别 stub（须先上传，file_id 归属该租户）──
        up_code, up = req_upload(
            "/admin/shop/onboarding/files",
            token,
            {"tenant_id": str(target_tenant_id), "doc_type": "business_license"},
        )
        fid = up.get("file_id") if isinstance(up, dict) else None
        code, ocr = req(
            "POST",
            "/admin/shop/onboarding/ocr",
            token=token,
            body={
                "doc_type": "business_license",
                "file_id": fid,
                "tenant_id": target_tenant_id,
            },
        )
        results.append(
            check(
                "E2E-F0-3 OCR证件识别",
                up_code == 201
                and bool(fid)
                and code == 200
                and ocr.get("stub") is True
                and "unified_social_credit_code" in ocr.get("fields", {}),
                str(code),
            )
        )

        # ── F0-4: 提交入驻申请 ──
        code, created = req(
            "POST",
            "/admin/shop/onboarding/applications",
            token=token,
            body={
                "tenant_id": target_tenant_id,
                "entity_type": "enterprise",
                "legal_name": prefill.get("legal_name", "E2E测试主体"),
                "display_name": prefill.get("display_name", "E2E测试商家"),
                "contact_name": "E2E联系人",
                "contact_mobile": "13900001234",
                "unified_social_credit_code": "91110000MA01234567",
                "legal_rep_name": "张三",
                "qualification_files": {},
                "ocr_results": [],
                "remark": "E2E F0 全流程验收",
            },
        )
        results.append(
            check(
                "E2E-F0-4 提交入驻申请",
                code == 201 and created.get("status") == "pending",
                str(code),
            )
        )
        app_id = created.get("id") if code == 201 else None

        # ── F0-5: 重复申请拦截 409 ──
        code, dup = req(
            "POST",
            "/admin/shop/onboarding/applications",
            token=token,
            body={
                "tenant_id": target_tenant_id,
                "entity_type": "enterprise",
                "legal_name": "重复申请主体",
                "contact_name": "测试",
                "contact_mobile": "13900001234",
                "unified_social_credit_code": "91110000MA01234567",
                "legal_rep_name": "张三",
            },
        )
        results.append(check("E2E-F0-5 重复申请拦截409", code == 409, str(code)))

        # ── F0-6: 审核中状态 ──
        code, reviewing = req(
            "GET",
            f"/admin/shop/merchants/{target_tenant_id}",
            token=token,
        )
        results.append(
            check(
                "E2E-F0-6 审核中状态",
                code == 200 and reviewing.get("onboarding_status") == "reviewing",
                str(reviewing.get("onboarding_status")),
            )
        )

        # ── F0-7: 待审申请列表 ──
        code, app_list = req(
            "GET",
            "/admin/shop/onboarding/applications?status=pending",
            token=token,
        )
        results.append(
            check(
                "E2E-F0-7 待审申请列表",
                code == 200 and app_list.get("total", 0) >= 1,
                str(app_list.get("total")),
            )
        )

        # ── F0-8: 审核通过 → 创建商家账号 ──
        if app_id:
            code, approved = req(
                "POST",
                f"/admin/shop/onboarding/applications/{app_id}/approve",
                token=token,
                body={
                    "plan_label": "7天试用基础版",
                    "trial_days": 7,
                    "store_quota": 1,
                },
            )
            results.append(
                check(
                    "E2E-F0-8 审核通过创建商家",
                    code == 200 and approved.get("merchant_id") is not None,
                    str(code),
                )
            )
        else:
            results.append(check("E2E-F0-8 审核通过创建商家", False, "无申请ID"))

        # ── F0-9: 商家列表含新入驻 ──
        code, merchants = req("GET", "/admin/shop/merchants", token=token)
        found_new = False
        if code == 200:
            for item in merchants.get("items", []):
                if str(item.get("tenant_id")) == str(target_tenant_id) and item.get("merchant_id"):
                    found_new = True
                    break
        results.append(
            check(
                "E2E-F0-9 商家列表含新入驻",
                code == 200 and found_new,
                str(merchants.get("total")),
            )
        )

        # ── F0-10: 商家详情 active ──
        code, detail = req(
            "GET",
            f"/admin/shop/merchants/{target_tenant_id}",
            token=token,
        )
        results.append(
            check(
                "E2E-F0-10 商家详情active",
                code == 200
                and detail.get("merchant_id") is not None
                and detail.get("onboarding_status") == "active",
                str(detail.get("onboarding_status")),
            )
        )

    else:
        # ── 无可用未入驻租户：跳过入驻流程，验证已有商家 ──
        print("[SKIP] E2E-F0-2~8 入驻全流程 — 无可用未入驻租户")

        # F0-9: 商家列表
        code, merchants = req("GET", "/admin/shop/merchants", token=token)
        results.append(
            check(
                "E2E-F0-9 商家列表",
                code == 200 and merchants.get("total", 0) >= 1,
                str(merchants.get("total")),
            )
        )

        # F0-10: 商家详情
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
                    "E2E-F0-10 商家详情",
                    code == 200
                    and detail.get("merchant_id") is not None
                    and detail.get("onboarding_status") in ("active", "suspended", "closed"),
                    str(detail.get("onboarding_status")),
                )
            )
        else:
            results.append(check("E2E-F0-10 商家详情", False, "无已入驻商家"))

    passed = sum(results)
    total = len(results)
    if total > 0:
        print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    else:
        print("\nSKIP 0/0")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
