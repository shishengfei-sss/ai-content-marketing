#!/usr/bin/env python3
"""支付安全验收：支付幂等性、密钥加密、签名验证。"""

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

    # ── SEC-10 支付幂等 + SEC-12 错误签名 ──
    from tests.shop_catalog_helper import (  # noqa: E402
        buyer_token,
        ensure_demo_merchant_admin,
        ensure_on_sale_product,
        resolve_tenant_id,
    )
    from app.services.shop.wechat_pay_service import stub_sign  # noqa: E402

    ensure_demo_merchant_admin()
    merchant = login("13900000099", "test123456")
    tenant_id = resolve_tenant_id(merchant)
    api_key = "mock_api_key_sec"
    pid = ensure_on_sale_product(merchant, "course", price_cents=19900)
    req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_sec",
            "wx_app_id": "wx_mock_appid_sec",
            "wx_api_key": api_key,
            "wx_notify_url": "http://127.0.0.1:8003/api/v1/mp/shop/payments/notify",
        },
    )
    buyer = buyer_token(tenant_id)
    req(
        "POST",
        "/mp/shop/auth/bind",
        token=buyer,
        body={"mobile": "136" + f"{int.from_bytes(os.urandom(4), 'big') % 10**8:08d}"},
    )
    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created or {}).get("order") or created
    order_id = order.get("id")
    order_no = order.get("order_no")
    amount = 19900

    bad = req(
        "POST",
        "/mp/shop/payments/notify",
        body={
            "order_no": order_no,
            "transaction_id": f"BAD{os.urandom(6).hex()}",
            "paid_amount_cents": amount,
            "sign": "deadbeef",
        },
    )
    results.append(
        check(
            "SEC-12 错误签名拒收",
            bad[0] == 400,
            f"code={bad[0]}",
        )
    )

    tx = f"TX{os.urandom(8).hex()}"
    sign = stub_sign(order_no, tx, amount, api_key)
    first = req(
        "POST",
        "/mp/shop/payments/notify",
        body={
            "order_no": order_no,
            "transaction_id": tx,
            "paid_amount_cents": amount,
            "sign": sign,
        },
    )
    second = req(
        "POST",
        "/mp/shop/payments/notify",
        body={
            "order_no": order_no,
            "transaction_id": tx,
            "paid_amount_cents": amount,
            "sign": sign,
        },
    )
    results.append(
        check(
            "SEC-10 支付回调幂等",
            first[0] == 200
            and (first[1] or {}).get("status") == "paid"
            and second[0] == 200
            and (second[1] or {}).get("status") == "paid",
            f"first={first[0]} second={second[0]}",
        )
    )

    # ── SEC-11 支付密钥加密（验证 crypto 服务存在且可逆）──
    from app.services.crypto import (  # noqa: E402
        decrypt_api_key,
        encrypt_api_key,
        mask_api_key,
    )

    test_plain = "wechat_pay_api_key_secret_2024"
    encrypted = encrypt_api_key(test_plain)
    decrypted = decrypt_api_key(encrypted)

    results.append(
        check(
            "SEC-11 加密服务存在且可逆",
            encrypted != test_plain and decrypted == test_plain,
            f"encrypted_len={len(encrypted)}, roundtrip_ok={decrypted == test_plain}",
        )
    )

    # 验证加密结果不是明文
    results.append(
        check(
            "SEC-11 加密后不含明文",
            test_plain not in encrypted,
            f"contains_plain={test_plain in encrypted}",
        )
    )

    # 验证空值处理
    results.append(
        check(
            "SEC-11 空值加密返回空串",
            encrypt_api_key("") == "" and decrypt_api_key("") == "",
            "empty handling ok",
        )
    )

    # 验证 mask_api_key 可用（支付密钥界面展示脱敏）
    masked = mask_api_key(test_plain)
    results.append(
        check(
            "SEC-11 密钥脱敏可用",
            "****" in masked and masked != test_plain,
            f"masked={masked}",
        )
    )

    passed = sum(results)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
