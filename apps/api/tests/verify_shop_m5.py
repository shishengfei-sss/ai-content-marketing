#!/usr/bin/env python3
"""M5 订单/退款/权益验收。对照执行计划 §9.2 VS-M5-01～05 + VM5 主路径。"""

from __future__ import annotations

import os
import sys
import uuid
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


def _ensure_merchant_token() -> tuple[str, str]:
    """返回 (merchant_token, tenant_id)。"""
    from app.database import SessionLocal, uuid_eq
    from app.models import TenantMembership, TenantRole, User
    from app.models.shop import ShopMerchantAccount
    from app.services.auth_service import hash_password

    phone = "13900000095"
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
                    "tenant_name": f"M5商户-{uuid.uuid4().hex[:6]}",
                    "display_name": "M5测试",
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


def _ensure_on_sale_product(merchant: str, product_type: str = "course") -> str:
    from tests.shop_catalog_helper import ensure_on_sale_product

    extra = {"refund_policy": "always_allow"}
    return ensure_on_sale_product(merchant, product_type, price_cents=19900, extra=extra)


def _buyer_login(tenant_id: str, openid: str) -> str:
    code, data = req(
        "POST",
        "/mp/shop/auth/login",
        body={"tenant_id": tenant_id, "code": f"mock:{openid}"},
    )
    assert code == 200, data
    return data["access_token"]


def _ensure_payment_config(merchant: str, api_key: str = "mock_api_key_001") -> str:
    code, data = req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_001",
            "wx_app_id": "wx_mock_appid_001",
            "wx_api_key": api_key,
            "wx_notify_url": "http://127.0.0.1:8003/api/v1/mp/shop/payments/notify",
        },
    )
    assert code == 200, data
    return api_key


def main() -> int:
    from app.services.shop.wechat_pay_service import stub_sign

    results: list[bool] = []
    merchant, tenant_id = _ensure_merchant_token()
    api_key = _ensure_payment_config(merchant)
    pid = _ensure_on_sale_product(merchant, "course")

    # 买家登录 + 绑手机
    buyer = _buyer_login(tenant_id, f"m5_{uuid.uuid4().hex[:10]}")
    mobile = "138" + f"{uuid.uuid4().int % 10**8:08d}"
    code, data = req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})
    results.append(check("VS-M5-LOGIN 绑定手机", code == 200 and data.get("mobile") == mobile, f"{code} {data}"))

    # 下单 pending_payment
    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created or {}).get("order") or created
    ok = (
        code == 200
        and order.get("status") == "pending_payment"
        and bool((created or {}).get("prepay"))
    )
    results.append(check("VS-M5-CREATE 下单 pending_payment", ok, f"{code} {created}"))
    order_id = order.get("id") if ok else None
    order_no = order.get("order_no") if ok else None

    # off_sale 不可下
    code_off, off_p = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={"type": "digital", "name": f"M5-off-{uuid.uuid4().hex[:4]}", "price_cents": 100},
    )
    if code_off == 200:
        code_bad, bad = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": off_p["id"]})
        results.append(check("VS-M5-OFF 未上架 409", code_bad == 409, f"{code_bad} {bad}"))
    else:
        results.append(check("VS-M5-OFF 未上架 409", False, str(off_p)))

    # 支付回调 → paid + entitlement
    tx = f"TX{uuid.uuid4().hex[:16]}"
    amount = 19900
    sign = stub_sign(order_no or "", tx, amount, api_key)
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
        check("VS-M5-PAY 支付回调 paid", code == 200 and paid.get("status") == "paid", f"{code} {paid}")
    )

    # 幂等回调
    code2, paid2 = req(
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
            "VS-M5-PAY-IDEM 回调幂等",
            code2 == 200 and paid2.get("status") == "paid",
            f"{code2} {paid2}",
        )
    )

    code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
    ent = None
    if code == 200 and ents.get("items"):
        ent = next((e for e in ents["items"] if e.get("order_id") == order_id), ents["items"][0])
    results.append(
        check(
            "VS-M5-ENT 权益 active",
            ent is not None and ent.get("status") == "active",
            f"{code} {ents}",
        )
    )
    ent_id = ent["id"] if ent else None

    # 商家列表脱敏 + A09 默认字段
    code, mlist = req("GET", "/shop/orders?page=1&page_size=20", token=merchant)
    masked_ok = False
    cols_ok = False
    if code == 200:
        row = next((i for i in mlist.get("items") or [] if i.get("id") == order_id), None)
        mm = (row or {}).get("buyer_mobile_masked") or ""
        masked_ok = "****" in mm and row is not None and row.get("buyer_mobile") is None
        cols_ok = bool(row) and bool(row.get("channel")) and "created_at" in row and "status_counts" in mlist
    results.append(check("VS-M5-05 列表手机号脱敏", masked_ok, f"{code}"))
    results.append(
        check("VS-M5-A09 列表含渠道/下单时间/status_counts", cols_ok, f"{code} {mlist.get('status_counts')}")
    )

    # 导出
    code_ex, _ex = req(
        "GET",
        f"/shop/orders/export?status=paid",
        token=merchant,
    )
    results.append(check("VS-M5-A09 导出 CSV", code_ex == 200, f"{code_ex}"))

    # 已开票后退款 → needs_red_flush
    if order_id:
        code, _ = req(
            "POST",
            f"/shop/orders/{order_id}/mark-invoice",
            token=merchant,
            body={"invoice_status": "issued"},
        )
        results.append(check("VS-M5-INV 标记已开票", code == 200, f"{code}"))
    else:
        results.append(check("VS-M5-INV 标记已开票", False, "no order"))

    # 部分退款 422
    if order_id:
        code, part = req(
            "POST",
            f"/shop/orders/{order_id}/refund",
            token=merchant,
            body={"amount_cents": 100, "reason": "部分"},
        )
        results.append(check("VS-M5-03 部分退款 422", code == 422, f"{code} {part}"))
    else:
        results.append(check("VS-M5-03 部分退款 422", False, "no order"))

    # 全额退款 → revoked
    if order_id:
        code, ref = req(
            "POST",
            f"/shop/orders/{order_id}/refund",
            token=merchant,
            body={"reason": "验收全额退"},
        )
        ok_ref = (
            code == 200
            and ref.get("status") == "succeeded"
            and ref.get("needs_red_flush") is True
        )
        results.append(check("VS-M5-01/05 全额退款+红冲标记", ok_ref, f"{code} {ref}"))
        refund_id = ref.get("id") if code == 200 else None
    else:
        results.append(check("VS-M5-01/05 全额退款+红冲标记", False, "no order"))
        refund_id = None

    if ent_id:
        code, ent2 = req("GET", "/mp/shop/entitlements", token=buyer)
        e2 = next((e for e in (ent2.get("items") or []) if e["id"] == ent_id), None)
        results.append(
            check(
                "VS-M5-01 entitlement=revoked",
                e2 is not None and e2.get("status") == "revoked",
                f"{code} {e2}",
            )
        )
        code, a = req("GET", f"/mp/shop/entitlements/{ent_id}/assert-active", token=buyer)
        results.append(check("VS-M5-02 revoked 履约 403", code == 403, f"{code} {a}"))
    else:
        results.append(check("VS-M5-01 entitlement=revoked", False, "no ent"))
        results.append(check("VS-M5-02 revoked 履约 403", False, "no ent"))

    # 重复退款回调幂等
    if refund_id:
        code, r2 = req("POST", f"/shop/refunds/{refund_id}/replay-notify", token=merchant)
        results.append(
            check(
                "VS-M5-04 退款回调幂等",
                code == 200 and r2.get("status") == "succeeded",
                f"{code} {r2}",
            )
        )
        # 再退一次应 409
        code, again = req(
            "POST",
            f"/shop/orders/{order_id}/refund",
            token=merchant,
            body={"reason": "再退"},
        )
        results.append(check("VS-M5-04b 已退款再退 409", code == 409, f"{code} {again}"))
    else:
        results.append(check("VS-M5-04 退款回调幂等", False, "no refund"))
        results.append(check("VS-M5-04b 已退款再退 409", False, "no refund"))

    # UI 文件
    web = API_ROOT.parents[1] / "apps" / "web" / "src" / "views" / "shop"
    ui_ok = (web / "OrdersList.vue").is_file()
    results.append(check("VS-M5-UI OrdersList 存在", ui_ok, str(web)))

    passed = sum(results)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
