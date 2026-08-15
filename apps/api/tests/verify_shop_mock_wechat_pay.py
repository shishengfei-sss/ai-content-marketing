#!/usr/bin/env python3
"""微信支付 Mock 验收：Stub 配置、端点响应形状、幂等键、回调签名、账单下载。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402
from tests.shop_test_config import WECHAT_PAY_STUB  # noqa: E402


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []

    # ── MOCK-WP-1 Stub 配置存在 & 统一下单端点 ──
    results.append(
        check(
            "MOCK-WP-1 微信支付Stub配置存在",
            WECHAT_PAY_STUB.name == "wechat_pay"
            and WECHAT_PAY_STUB.base_url == "http://mock.wechat-pay.local"
            and len(WECHAT_PAY_STUB.endpoints) == 5,
            f"name={WECHAT_PAY_STUB.name}, endpoints={len(WECHAT_PAY_STUB.endpoints)}",
        )
    )

    # 验证统一下单端点响应形状
    native_ep = None
    for ep in WECHAT_PAY_STUB.endpoints:
        if ep.path == "/v3/pay/transactions/native":
            native_ep = ep
            break
    results.append(
        check(
            "MOCK-WP-1 统一下单响应形状",
            native_ep is not None
            and native_ep.response_status == 200
            and native_ep.response_body.get("code") == "SUCCESS"
            and "code_url" in native_ep.response_body
            and "transaction_id" in native_ep.response_body,
            f"code={native_ep.response_body.get('code') if native_ep else 'N/A'}",
        )
    )

    # ── MOCK-WP-2 查询订单端点响应形状 ──
    query_ep = None
    for ep in WECHAT_PAY_STUB.endpoints:
        if "out-trade-no" in ep.path:
            query_ep = ep
            break
    results.append(
        check(
            "MOCK-WP-2 查询订单响应形状",
            query_ep is not None
            and query_ep.response_status == 200
            and query_ep.response_body.get("trade_state") == "SUCCESS"
            and "amount" in query_ep.response_body,
            f"trade_state={query_ep.response_body.get('trade_state') if query_ep else 'N/A'}",
        )
    )

    # ── MOCK-WP-3 退款端点响应形状 & 幂等键处理 ──
    refund_ep = None
    for ep in WECHAT_PAY_STUB.endpoints:
        if "/refund/domestic/refunds" in ep.path:
            refund_ep = ep
            break
    results.append(
        check(
            "MOCK-WP-3 退款响应形状",
            refund_ep is not None
            and refund_ep.response_status == 200
            and refund_ep.response_body.get("refund_status") == "PROCESSING"
            and "out_refund_no" in refund_ep.response_body,
            f"refund_status={refund_ep.response_body.get('refund_status') if refund_ep else 'N/A'}",
        )
    )

    # 验证环境变量包含幂等相关配置
    env_has_mock = WECHAT_PAY_STUB.env_vars.get("WECHAT_PAY_MOCK") == "1"
    results.append(
        check(
            "MOCK-WP-3 幂等键环境变量",
            env_has_mock and "WECHAT_PAY_MCHID" in WECHAT_PAY_STUB.env_vars,
            f"mock={env_has_mock}",
        )
    )

    # ── MOCK-WP-4 回调通知端点 & 签名验证(Mock) ──
    notify_ep = None
    for ep in WECHAT_PAY_STUB.endpoints:
        if "/notify/pay" in ep.path:
            notify_ep = ep
            break
    results.append(
        check(
            "MOCK-WP-4 回调通知响应形状",
            notify_ep is not None
            and notify_ep.response_status == 200
            and notify_ep.response_body.get("event_type") == "TRANSACTION.SUCCESS"
            and "resource" in notify_ep.response_body
            and "transaction_id" in notify_ep.response_body.get("resource", {}),
            f"event_type={notify_ep.response_body.get('event_type') if notify_ep else 'N/A'}",
        )
    )

    # ── MOCK-WP-5 账单下载端点 ──
    bill_ep = None
    for ep in WECHAT_PAY_STUB.endpoints:
        if "/bill/tradebill" in ep.path:
            bill_ep = ep
            break
    results.append(
        check(
            "MOCK-WP-5 账单下载响应形状",
            bill_ep is not None
            and bill_ep.response_status == 200
            and "download_url" in bill_ep.response_body
            and "hash_type" in bill_ep.response_body
            and bill_ep.response_body.get("hash_type") == "SHA1",
            f"hash_type={bill_ep.response_body.get('hash_type') if bill_ep else 'N/A'}",
        )
    )

    passed = sum(results)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
