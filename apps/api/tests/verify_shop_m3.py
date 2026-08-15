#!/usr/bin/env python3
"""M3 私域支付硬验收。对照执行计划 §7.2 VS-M3-01～07。"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")
os.environ.setdefault("WECHAT_PAY_MODE", "stub")
os.environ.setdefault("WECHAT_PAY_MOCK", "1")

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def _ensure_merchant_token() -> tuple[str, str]:
    from app.database import SessionLocal, uuid_eq
    from app.models import TenantMembership, TenantRole, User
    from app.models.shop import ShopMerchantAccount
    from app.services.auth_service import hash_password

    phone = "13900000093"
    password = "test123456"
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            db.close()
            code, data = req(
                "POST",
                "/auth/register",
                body={
                    "phone": phone,
                    "password": password,
                    "tenant_name": f"M3商户-{uuid.uuid4().hex[:6]}",
                    "display_name": "M3测试",
                },
            )
            assert code in (200, 201), data
            db = SessionLocal()
            user = db.query(User).filter(User.phone == phone).first()

        merchant = (
            db.query(ShopMerchantAccount)
            .filter(ShopMerchantAccount.status == "active")
            .order_by(ShopMerchantAccount.created_at.desc())
            .first()
        )
        if not merchant:
            raise RuntimeError("no active merchant")

        mem = (
            db.query(TenantMembership)
            .filter(
                uuid_eq(TenantMembership.user_id, user.id),
                uuid_eq(TenantMembership.tenant_id, merchant.tenant_id),
            )
            .first()
        )
        role = (
            db.query(TenantRole)
            .filter(
                uuid_eq(TenantRole.tenant_id, merchant.tenant_id),
                TenantRole.code == "shop_admin",
            )
            .first()
        )
        if role is None:
            role = (
                db.query(TenantRole)
                .filter(uuid_eq(TenantRole.tenant_id, merchant.tenant_id))
                .order_by(TenantRole.created_at.asc())
                .first()
            )
        if mem is None and role is not None:
            db.add(
                TenantMembership(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    tenant_id=merchant.tenant_id,
                    role_id=role.id,
                    is_active=True,
                )
            )
        elif mem is not None and role is not None:
            mem.role_id = role.id
            mem.is_active = True
        user.tenant_id = merchant.tenant_id
        user.hashed_password = hash_password(password)
        db.commit()
        tenant_id = str(merchant.tenant_id)
    finally:
        db.close()
    return login(phone, password), tenant_id


def _ensure_on_sale_product(merchant: str) -> str:
    from tests.shop_catalog_helper import ensure_on_sale_product

    return ensure_on_sale_product(merchant, "course", price_cents=9900)


def main() -> int:
    from app.database import SessionLocal
    from app.models.crm import Contact
    from app.models.shop import ShopEntitlement
    from app.services.shop.wechat_pay_service import stub_sign

    results: list[bool] = []
    api_key = "mock_api_key_m3"
    merchant, tenant_id = _ensure_merchant_token()

    # 支付配置
    code, cfg = req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_001",
            "wx_app_id": "wx_mock_appid_001",
            "wx_api_key": api_key,
        },
    )
    results.append(
        check("VS-M3-CFG 支付配置保存", code == 200 and bool(cfg.get("wx_mch_id")), f"{code} {cfg}")
    )

    code, test = req("POST", "/shop/payment-config/test", token=merchant, body={})
    results.append(
        check("VS-M3-CFG-TEST stub 联通", code == 200 and test.get("ok") is True, f"{code} {test}")
    )

    pid = _ensure_on_sale_product(merchant)

    # VS-M3-05 未登录下单
    code, anon = req("POST", "/mp/shop/orders", body={"product_id": pid})
    results.append(check("VS-M3-05 未登录 401", code == 401, f"{code} {anon}"))

    # 买家登录（计 Contact 数）
    db = SessionLocal()
    try:
        contacts_before = db.query(Contact).count()
    finally:
        db.close()

    code, login_data = req(
        "POST",
        "/mp/shop/auth/login",
        body={"tenant_id": tenant_id, "code": f"mock:m3_{uuid.uuid4().hex[:10]}"},
    )
    assert code == 200, login_data
    buyer = login_data["access_token"]
    mobile = "139" + f"{uuid.uuid4().int % 10**8:08d}"
    code, _ = req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})
    assert code == 200, _

    # 篡改金额
    code, bad_amt = req(
        "POST",
        "/mp/shop/orders",
        token=buyer,
        body={"product_id": pid, "amount_cents": 1},
    )
    results.append(check("VS-M3-AMT 篡改金额 422", code == 422, f"{code} {bad_amt}"))

    # 下单 + prepay
    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created or {}).get("order") or {}
    prepay = (created or {}).get("prepay") or {}
    results.append(
        check(
            "VS-M3-PREPAY 下单返回 prepay_id",
            code == 200
            and order.get("status") == "pending_payment"
            and bool(prepay.get("prepay_id")),
            f"{code} {created}",
        )
    )
    order_id = order.get("id")
    order_no = order.get("order_no")
    amount = int(order.get("amount_cents") or 9900)

    # VS-M3-06 非 on_sale
    code_d, draft = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={"type": "digital", "name": f"M3-draft-{uuid.uuid4().hex[:4]}", "price_cents": 100},
    )
    if code_d == 200:
        code_bad, bad = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": draft["id"]})
        results.append(check("VS-M3-06 非 on_sale 不可下单", code_bad == 409, f"{code_bad} {bad}"))
    else:
        results.append(check("VS-M3-06 非 on_sale 不可下单", False, str(draft)))

    # VS-M3-04 错误签名
    bad_tx = f"BAD{uuid.uuid4().hex[:12]}"
    code, bad_sign = req(
        "POST",
        "/mp/shop/payments/notify",
        body={
            "order_no": order_no,
            "transaction_id": bad_tx,
            "paid_amount_cents": amount,
            "sign": "deadbeef",
        },
    )
    code_st, still = req("GET", f"/mp/shop/orders/{order_id}", token=buyer)
    results.append(
        check(
            "VS-M3-04 错误签名不改状态",
            code == 400 and still.get("status") == "pending_payment",
            f"notify={code} {bad_sign}; order={code_st} {still}",
        )
    )

    # VS-M3-01 Mock 支付
    tx = f"TX{uuid.uuid4().hex[:16]}"
    sign = stub_sign(order_no, tx, amount, api_key)
    code, paid = req(
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
        check("VS-M3-01 下单→Mock付→paid", code == 200 and paid.get("status") == "paid", f"{code} {paid}")
    )

    # VS-M3-02 entitlement active
    code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
    items = ents.get("items") or []
    ent = next((e for e in items if e.get("order_id") == order_id), None)
    results.append(
        check(
            "VS-M3-02 entitlement active+order_id",
            ent is not None and ent.get("status") == "active",
            f"{code} {ents}",
        )
    )

    # VS-M3-03 重放 10 次
    for _i in range(10):
        req(
            "POST",
            "/mp/shop/payments/notify",
            body={
                "order_no": order_no,
                "transaction_id": tx,
                "paid_amount_cents": amount,
                "sign": sign,
            },
        )
    db = SessionLocal()
    try:
        from app.database import uuid_eq

        cnt = (
            db.query(ShopEntitlement)
            .filter(uuid_eq(ShopEntitlement.order_id, uuid.UUID(order_id)))
            .count()
        )
    finally:
        db.close()
    results.append(check("VS-M3-03 重放 notify entitlement=1", cnt == 1, f"count={cnt}"))

    # VS-M3-07 不写 contacts
    db = SessionLocal()
    try:
        contacts_after = db.query(Contact).count()
    finally:
        db.close()
    results.append(
        check(
            "VS-M3-07 未创建 contacts 买家",
            contacts_after == contacts_before,
            f"before={contacts_before} after={contacts_after}",
        )
    )

    # 金额不符
    order2_code, created2 = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    o2 = (created2 or {}).get("order") or {}
    if order2_code == 200 and o2.get("order_no"):
        tx2 = f"TX{uuid.uuid4().hex[:16]}"
        wrong_amt = amount + 1
        sign2 = stub_sign(o2["order_no"], tx2, wrong_amt, api_key)
        code_w, wr = req(
            "POST",
            "/mp/shop/payments/notify",
            body={
                "order_no": o2["order_no"],
                "transaction_id": tx2,
                "paid_amount_cents": wrong_amt,
                "sign": sign2,
            },
        )
        results.append(check("VS-M3-AMT-MISMATCH 金额不符 422", code_w == 422, f"{code_w} {wr}"))
    else:
        results.append(check("VS-M3-AMT-MISMATCH 金额不符 422", False, str(created2)))

    passed = sum(results)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
