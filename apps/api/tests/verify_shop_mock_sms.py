#!/usr/bin/env python3
"""短信 Mock 验收：Stub 配置、验证码发送、内存日志验证。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, clear_sms_rate_limits, req  # noqa: E402
from tests.shop_test_config import SMS_STUB  # noqa: E402


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []

    # ── MOCK-SMS-1 SMS Stub 配置存在 ──
    results.append(
        check(
            "MOCK-SMS-1 SMS Stub配置存在",
            SMS_STUB.name == "sms"
            and SMS_STUB.base_url == "http://mock.sms.local"
            and len(SMS_STUB.endpoints) == 3,
            f"name={SMS_STUB.name}, endpoints={len(SMS_STUB.endpoints)}",
        )
    )

    # 验证 send-code 端点响应形状
    send_ep = None
    for ep in SMS_STUB.endpoints:
        if ep.path == "/sms/send-code":
            send_ep = ep
            break
    results.append(
        check(
            "MOCK-SMS-1 发送验证码Stub响应形状",
            send_ep is not None
            and send_ep.response_status == 200
            and send_ep.response_body.get("data", {}).get("sent") is True
            and send_ep.response_body.get("data", {}).get("stub") is True,
            f"sent={send_ep.response_body.get('data', {}).get('sent') if send_ep else 'N/A'}",
        )
    )

    # ── MOCK-SMS-2 通过真实 API 发送验证码(Mock 模式) ──
    clear_sms_rate_limits()
    test_phone = "13900000099"
    code, resp = req("POST", "/auth/password/forgot/send-code", body={"phone": test_phone})
    results.append(
        check(
            "MOCK-SMS-2 验证码发送(Mock模式)",
            code == 200 and "mock_hint" in (resp if isinstance(resp, dict) else {}),
            f"code={code}, resp_keys={list(resp.keys()) if isinstance(resp, dict) else resp}",
        )
    )

    # ── MOCK-SMS-3 验证 SMS 已写入内存 Store ──
    from app.services import sms_service  # noqa: E402

    store_key = f"{test_phone}:reset_password"
    entry = sms_service._store.get(store_key)
    results.append(
        check(
            "MOCK-SMS-3 SMS内存Store已记录",
            entry is not None and "code" in entry and "expire_at" in entry,
            f"entry_keys={list(entry.keys()) if entry else 'None'}",
        )
    )

    # 验证 mock_hint 中包含 mock 验证码
    mock_hint = resp.get("mock_hint", "") if isinstance(resp, dict) else ""
    stored_code = str(entry.get("code", "")) if entry else ""
    results.append(
        check(
            "MOCK-SMS-3 Mock验证码一致性",
            mock_hint != "" and stored_code != "" and stored_code in mock_hint,
            f"hint={mock_hint}, stored_code={'***' if stored_code else 'empty'}",
        )
    )

    passed = sum(results)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
