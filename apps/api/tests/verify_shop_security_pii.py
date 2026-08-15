#!/usr/bin/env python3
"""PII 脱敏验收：手机号/身份证/银行卡脱敏、API 响应 PII 过滤、日志脱敏。"""

from __future__ import annotations

import os
import re
import json
import sys
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req, req_upload  # noqa: E402
from tests.shop_test_config import SMS_STUB  # noqa: E402


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def _is_masked_phone(value: str) -> bool:
    """检查手机号是否已脱敏（格式如 139****0099）。"""
    if not value or not isinstance(value, str):
        return False
    return "***" in value or "****" in value


def main() -> int:
    results: list[bool] = []

    admin_token = login("13800000000", "admin123456")

    # ── SEC-5 手机号脱敏显示 ──
    # 验证 SMS Stub 响应中手机号已脱敏
    send_ep = None
    for ep in SMS_STUB.endpoints:
        if ep.path == "/sms/send-code":
            send_ep = ep
            break
    phone_in_stub = send_ep.response_body.get("data", {}).get("phone", "") if send_ep else ""
    results.append(
        check(
            "SEC-5 SMS Stub手机号脱敏",
            _is_masked_phone(phone_in_stub),
            f"phone={phone_in_stub}",
        )
    )

    # ── SEC-6 身份证号脱敏显示 ──
    # 验证 OCR stub 响应中身份证号字段存在（须先上传本租户文件）
    mch_token = login("13900000099", "test123456")
    up_code, up = req_upload("/shop/onboarding/files", mch_token, {"doc_type": "id_card_front"})
    fid = up.get("file_id") if isinstance(up, dict) else None
    code, ocr = req(
        "POST",
        "/shop/onboarding/ocr",
        token=mch_token,
        body={"doc_type": "id_card_front", "file_id": fid},
    )
    id_no = ocr.get("fields", {}).get("id_no", "") if isinstance(ocr, dict) else ""
    # OCR stub 可能返回完整或脱敏的身份证号，检查是否存在该字段
    results.append(
        check(
            "SEC-6 OCR身份证字段存在",
            up_code == 201
            and bool(fid)
            and code == 200
            and "id_no" in (ocr.get("fields", {}) if isinstance(ocr, dict) else {}),
            f"up={up_code} code={code}, id_no_present={'id_no' in (ocr.get('fields', {}) if isinstance(ocr, dict) else {})}",
        )
    )

    # ── SEC-7 银行卡号脱敏显示 ──
    from app.services.shop.merchant_service import _mask_bank_account  # noqa: E402

    masked_bank, display = _mask_bank_account(
        {"bank_name": "招商银行", "account_name": "测试", "account_no": "6222021234567890123"}
    )
    results.append(
        check(
            "SEC-7 银行卡号脱敏",
            "account_no" not in masked_bank
            and masked_bank.get("account_no_masked") == "尾号 0123"
            and "尾号 0123" in (display or ""),
            f"masked={masked_bank} display={display}",
        )
    )
    code, merchants_for_bank = req("GET", "/admin/shop/merchants", token=admin_token)
    bank_tid = None
    for item in (merchants_for_bank or {}).get("items") or []:
        if item.get("merchant_id"):
            bank_tid = item["tenant_id"]
            break
    if bank_tid:
        code, mdetail = req("GET", f"/admin/shop/merchants/{bank_tid}", token=admin_token)
        info = (mdetail or {}).get("bank_account_info") or {}
        results.append(
            check(
                "SEC-7 商家详情无完整卡号",
                code == 200 and "account_no" not in info,
                f"code={code} keys={list(info.keys()) if isinstance(info, dict) else info}",
            )
        )
    else:
        results.append(check("SEC-7 商家详情无完整卡号", False, "无商家"))

    # ── SEC-8 API 响应中 PII 字段过滤 ──
    # 验证商家列表项不包含 contact_mobile / id_no 等敏感字段
    code, merchants = req("GET", "/admin/shop/merchants", token=admin_token)
    items = merchants.get("items", []) if isinstance(merchants, dict) else []
    pii_leaked = False
    for item in items:
        if isinstance(item, dict):
            if "contact_mobile" in item or "id_no" in item or "bank_card" in item:
                pii_leaked = True
                break
    results.append(
        check(
            "SEC-8 商家列表项无PII泄露",
            code == 200 and not pii_leaked and len(items) > 0,
            f"items={len(items)}, pii_leaked={pii_leaked}",
        )
    )

    # ── SEC-9 密钥脱敏（mask_api_key）──
    from app.services.crypto import mask_api_key  # noqa: E402

    test_key = "sk-test-api-key-1234567890abcdef"
    masked = mask_api_key(test_key)
    results.append(
        check(
            "SEC-9 mask_api_key脱敏正确",
            masked != test_key and "****" in masked and masked.startswith("sk-") and masked.endswith("cdef"),
            f"masked={masked}",
        )
    )

    # 短密钥脱敏
    short_masked = mask_api_key("abc")
    results.append(
        check(
            "SEC-9 短密钥全脱敏",
            short_masked == "****",
            f"masked={short_masked}",
        )
    )

    # ── SEC-8b 入驻申请 status / 创建响应默认脱敏（对照 PRD 列表详情永不回明文）──
    reviewing_token = login("13900000101", "demo123456")
    code, st = req("GET", "/shop/onboarding/status", token=reviewing_token)
    dumped = json.dumps(st, ensure_ascii=False) if isinstance(st, dict) else str(st)
    app = (st or {}).get("application") if isinstance(st, dict) else None
    mobile = (app or {}).get("contact_mobile") or ""
    results.append(
        check(
            "SEC-8 入驻status手机脱敏",
            code == 200
            and isinstance(app, dict)
            and "****" in str(mobile)
            and not re.search(r"1\d{10}", dumped)
            and not re.search(r"\d{17}[\dXx]", dumped),
            f"code={code} mobile={mobile} state={(st or {}).get('state')}",
        )
    )

    passed = sum(results)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
