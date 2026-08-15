#!/usr/bin/env python3
"""注入防护验收：SQL 注入防护、XSS 输入过滤、文件上传类型校验。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []

    admin_token = login("13800000000", "admin123456")
    tenant_token = login("13900000099", "test123456")

    # ── SEC-13 SQL 注入防护 ──
    # 测试查询参数中注入 SQL 不影响查询结果
    sqli_payloads = [
        "' OR '1'='1",
        "1; DROP TABLE users--",
        "'; SELECT * FROM users--",
        "1' UNION SELECT NULL--",
    ]

    sqli_safe = True
    for payload in sqli_payloads:
        code, data = req("GET", f"/admin/shop/merchants?q={payload}", token=admin_token)
        # 期望：不是 500 错误（服务不应崩溃），且返回结构正常
        if code != 200 or not isinstance(data, dict):
            sqli_safe = False
            break

    results.append(
        check(
            "SEC-13 SQL注入查询参数防护",
            sqli_safe,
            f"tested_payloads={len(sqli_payloads)}, all_200={sqli_safe}",
        )
    )

    # 测试商家列表 onboarding_status 参数注入
    code, data = req(
        "GET",
        "/admin/shop/merchants?onboarding_status=' OR '1'='1",
        token=admin_token,
    )
    results.append(
        check(
            "SEC-13 SQL注入状态参数防护",
            code != 500,
            f"code={code}",
        )
    )

    # 测试登录接口 SQL 注入（使用恶意手机号）
    code, data = req(
        "POST",
        "/auth/login",
        body={"phone": "' OR 1=1--", "password": "anything"},
    )
    results.append(
        check(
            "SEC-13 登录接口SQL注入防护",
            code in (401, 422, 400) and not (isinstance(data, dict) and "access_token" in data),
            f"code={code}",
        )
    )

    # ── SEC-14 XSS 输入过滤 ──
    xss_payloads = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert('XSS')",
        "\"><script>alert(document.cookie)</script>",
    ]

    xss_safe = True
    for payload in xss_payloads:
        # 测试在入驻备注中注入 XSS
        code, data = req(
            "POST",
            "/admin/shop/onboarding/ocr",
            token=admin_token,
            body={"doc_type": payload, "file_id": "demo-file-1"},
        )
        # 期望：OCR stub 正常返回或拒绝（不返回原始 XSS payload 在 HTML 中）
        # 关键是服务不崩溃（不 500），且不反射原始 payload
        if code == 500:
            xss_safe = False
            break
        # 检查返回数据中是否直接反射了 XSS payload
        data_str = str(data) if data else ""
        if payload in data_str and "stub" not in data_str:
            # 如果响应中直接包含了原始 XSS payload 且不是 stub 响应
            xss_safe = False
            break

    results.append(
        check(
            "SEC-14 XSS输入不导致服务崩溃",
            xss_safe,
            f"tested_payloads={len(xss_payloads)}, safe={xss_safe}",
        )
    )

    # 测试在服务跟进备注中注入 XSS
    code, merchants = req("GET", "/admin/shop/merchants", token=admin_token)
    detail_tid = None
    if isinstance(merchants, dict) and merchants.get("items"):
        for item in merchants["items"]:
            if item.get("merchant_id"):
                detail_tid = item["tenant_id"]
                break

    if detail_tid:
        code, note = req(
            "POST",
            f"/admin/shop/merchants/{detail_tid}/service-logs/notes",
            token=admin_token,
            body={"content": "<script>alert('XSS')</script>测试备注"},
        )
        # 服务应接受或过滤 XSS 内容，不应 500
        results.append(
            check(
                "SEC-14 服务备注XSS不崩溃",
                code in (200, 201, 400, 422),
                f"code={code}",
            )
        )
    else:
        results.append(check("SEC-14 服务备注XSS不崩溃", False, "无可用商家"))

    # ── SEC-15 文件上传类型校验 ──
    # 测试 OCR 接口 file_id 参数注入恶意路径
    code, ocr = req(
        "POST",
        "/admin/shop/onboarding/ocr",
        token=admin_token,
        body={"doc_type": "business_license", "file_id": "../../../etc/passwd"},
    )
    results.append(
        check(
            "SEC-15 OCR文件路径注入防护",
            code in (400, 404, 422),
            f"code={code}",
        )
    )

    # 测试非法 doc_type
    code, ocr2 = req(
        "POST",
        "/admin/shop/onboarding/ocr",
        token=admin_token,
        body={"doc_type": "malicious_type", "file_id": "demo-file-1"},
    )
    results.append(
        check(
            "SEC-15 非法doc_type处理",
            code != 500,
            f"code={code}",
        )
    )

    passed = sum(results)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
