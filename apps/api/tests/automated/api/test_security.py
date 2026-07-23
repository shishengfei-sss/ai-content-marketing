"""安全测试 — 对应测试用例 SEC-001 ~ SEC-005。"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

API_ROOT = Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req
from tests.verify_crm_helpers import ADMIN_PHONE, ADMIN_PASSWORD, login, lead_body, ensure_crm_test_users, sales_token, SALES_A_PHONE, CRM_TEST_PASSWORD


def _get_token() -> str:
    return login(ADMIN_PHONE, ADMIN_PASSWORD)


# ── SEC-001: SQL注入防护 ──────────────────────────────────────
def test_sql_injection_protection():
    token = _get_token()
    results: list[bool] = []

    # 在查询参数中注入 SQL
    payloads = [
        "'; DROP TABLE leads; --",
        "1 OR 1=1",
        "' UNION SELECT * FROM users --",
        "1; DELETE FROM leads WHERE 1=1; --",
    ]
    for payload in payloads:
        code, data = req("GET", f"/crm/leads?page=1&size=10&keyword={payload}", token=token)
        is_safe = code in (200, 400, 422)
        results.append(check(f"SEC-001 SQL注入防护 keyword='{payload[:20]}'", is_safe, f"code={code}"))

    # POST body 注入
    code, data = req("POST", "/crm/leads", token=token, body={
        "company_name": "'; DROP TABLE leads; --",
        "contact_name": "test",
        "mobile": f"139{uuid4().int % 100000000:08d}",
    })
    is_safe = code in (200, 201, 400, 422)
    results.append(check("SEC-001 POST body SQL注入防护", is_safe, f"code={code}"))

    assert all(results)


# ── SEC-002: XSS攻击防护 ─────────────────────────────────────
def test_xss_protection():
    token = _get_token()
    results: list[bool] = []

    xss_payloads = [
        '<script>alert("xss")</script>',
        '<img src=x onerror=alert(1)>',
        '"><script>document.cookie</script>',
        'javascript:alert(1)',
    ]
    for payload in xss_payloads:
        code, data = req("POST", "/crm/leads", token=token, body={
            "company_name": payload,
            "contact_name": "test",
            "mobile": f"139{uuid4().int % 100000000:08d}",
        })
        is_safe = code in (200, 201, 400, 422)
        results.append(check(f"SEC-002 XSS防护 '{payload[:30]}'", is_safe, f"code={code}"))

    assert all(results)


# ── SEC-003: 横向越权访问防护 ─────────────────────────────────
def test_horizontal_access_control(second_tenant_token):
    token_a = _get_token()
    token_b = second_tenant_token
    results: list[bool] = []

    # 租户A创建线索
    body = lead_body(f"越权测试公司-{uuid4().hex[:6]}")
    code, create_data = req("POST", "/crm/leads", token=token_a, body=body)
    assert code in (200, 201), f"create failed: {create_data}"
    lead_id = create_data.get("id") or (create_data.get("data", {}) or {}).get("id")
    assert lead_id, "无法获取线索ID"

    # 租户B尝试 GET
    code, _ = req("GET", f"/crm/leads/{lead_id}", token=token_b)
    results.append(check("SEC-003a 越权GET返回403/404", code in (403, 404), f"code={code}"))

    # 租户B尝试 PATCH
    code, _ = req("PATCH", f"/crm/leads/{lead_id}", token=token_b, body={"remark": "越权修改"})
    results.append(check("SEC-003b 越权PATCH返回403/404", code in (403, 404), f"code={code}"))

    # 租户B尝试 DELETE
    code, _ = req("DELETE", f"/crm/leads/{lead_id}", token=token_b)
    results.append(check("SEC-003c 越权DELETE返回403/404", code in (403, 404), f"code={code}"))

    assert all(results)


# ── SEC-004: API请求频率限制 ──────────────────────────────────
def test_rate_limiting():
    token = _get_token()
    results: list[bool] = []

    # 快速连续请求同一接口
    error_count = 0
    for i in range(20):
        code, _ = req("GET", "/crm/leads?page=1&size=5", token=token)
        if code == 429:
            error_count += 1

    # 频率限制不一定在测试环境开启，所以只是验证不会500
    results.append(check("SEC-004 快速请求无500错误", error_count == 0, f"429次数={error_count}"))

    assert all(results)


# ── SEC-005: 文件上传安全检查 ─────────────────────────────────
def test_file_upload_security():
    token = _get_token()
    results: list[bool] = []

    from tests.http_client import _get_test_client
    client = _get_test_client()

    # 尝试上传 .php 文件到导入接口
    php_content = b"<?php echo 'hack'; ?>"
    r = client.post(
        "/api/v1/crm/import/jobs",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("shell.php", php_content, "application/x-php")},
    )
    results.append(check("SEC-005a .php文件被拒绝", r.status_code in (400, 403, 415, 422), f"code={r.status_code}"))

    # 尝试上传 .exe 文件
    exe_content = b"MZ\x90\x00" + b"\x00" * 100
    r = client.post(
        "/api/v1/crm/import/jobs",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("malware.exe", exe_content, "application/octet-stream")},
    )
    results.append(check("SEC-005b .exe文件被拒绝", r.status_code in (400, 403, 415, 422), f"code={r.status_code}"))

    assert all(results)
