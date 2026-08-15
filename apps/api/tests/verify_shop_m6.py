#!/usr/bin/env python3
"""M6 核销/预约/开票验收。对照执行计划 §10.2 VS-M6-01～05 + VM6 主路径。"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, timedelta
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
    from app.database import SessionLocal, uuid_eq
    from app.models import TenantMembership, TenantRole, User
    from app.models.shop import ShopMerchantAccount
    from app.services.auth_service import hash_password

    phone = "13900000096"
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
                    "tenant_name": f"M6商户-{uuid.uuid4().hex[:6]}",
                    "display_name": "M6测试",
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


def _ensure_clerk_token(tenant_id: str) -> str:
    from app.database import SessionLocal, uuid_eq
    from app.models import TenantMembership, TenantRole, User
    from app.permissions import SHOP_CLERK_DEFAULT_PERMISSIONS, SYSTEM_ROLE_SHOP_CLERK
    from app.services.auth_service import hash_password
    from app.services.membership_service import _add_role_permissions

    phone = "13900000097"
    password = "test123456"
    db = SessionLocal()
    try:
        from uuid import UUID

        tid = UUID(tenant_id)
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            user = User(
                id=uuid.uuid4(),
                phone=phone,
                hashed_password=hash_password(password),
                display_name="M6店员",
                tenant_id=tid,
            )
            db.add(user)
            db.flush()
        role = (
            db.query(TenantRole)
            .filter(uuid_eq(TenantRole.tenant_id, tid), TenantRole.code == SYSTEM_ROLE_SHOP_CLERK)
            .first()
        )
        if role is None:
            role = TenantRole(
                id=uuid.uuid4(),
                tenant_id=tid,
                code=SYSTEM_ROLE_SHOP_CLERK,
                name="店员",
                is_system=True,
            )
            db.add(role)
            db.flush()
            _add_role_permissions(db, role.id, SHOP_CLERK_DEFAULT_PERMISSIONS)
        mem = (
            db.query(TenantMembership)
            .filter(uuid_eq(TenantMembership.user_id, user.id), uuid_eq(TenantMembership.tenant_id, tid))
            .first()
        )
        if mem is None:
            db.add(
                TenantMembership(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    tenant_id=tid,
                    role_id=role.id,
                    is_active=True,
                )
            )
        else:
            mem.role_id = role.id
            mem.is_active = True
        user.tenant_id = tid
        user.hashed_password = hash_password(password)
        db.commit()
    finally:
        db.close()
    return login(phone, password)


def _ensure_on_sale_product(merchant: str, product_type: str = "service", times: int = 2) -> str:
    from tests.shop_catalog_helper import ensure_on_sale_product

    extra = {"refund_policy": "always_allow"}
    if product_type == "service":
        extra["service_times"] = times
    return ensure_on_sale_product(merchant, product_type, price_cents=9900, extra=extra)


def _buyer_login(tenant_id: str, openid: str) -> str:
    code, data = req(
        "POST",
        "/mp/shop/auth/login",
        body={"tenant_id": tenant_id, "code": f"mock:{openid}"},
    )
    assert code == 200, data
    return data["access_token"]


def _ensure_payment_config(merchant: str, api_key: str = "mock_api_key_m6") -> str:
    code, data = req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_m6",
            "wx_app_id": "wx_mock_appid_m6",
            "wx_api_key": api_key,
            "wx_notify_url": "http://127.0.0.1:8003/api/v1/mp/shop/payments/notify",
        },
    )
    assert code == 200, data
    return api_key


def _pay_order(order_no: str, amount: int, api_key: str):
    from app.services.shop.wechat_pay_service import stub_sign

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
    assert code == 200 and paid.get("status") == "paid", paid
    return paid


def main() -> int:
    results: list[bool] = []

    merchant, tenant_id = _ensure_merchant_token()
    api_key = _ensure_payment_config(merchant)
    pid = _ensure_on_sale_product(merchant, "service", times=2)
    course_pid = _ensure_on_sale_product(merchant, "course")

    buyer = _buyer_login(tenant_id, f"m6_{uuid.uuid4().hex[:10]}")
    mobile = "138" + f"{uuid.uuid4().int % 10**8:08d}"
    code, data = req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})
    results.append(check("VS-M6-SETUP 绑定手机", code == 200, f"{code} {data}"))

    # 服务商品下单支付
    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created or {}).get("order") or created
    assert code == 200, created
    order_id = order["id"]
    order_no = order["order_no"]
    _pay_order(order_no, 9900, api_key)

    code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
    ent = next((e for e in (ents.get("items") or []) if e.get("order_id") == order_id), None)
    vc = (ent or {}).get("verify_code") or ""
    results.append(
        check(
            "VM6-SETUP 权益+6位核销码",
            ent is not None
            and ent.get("status") == "active"
            and isinstance(vc, str)
            and len(vc) == 6
            and vc.isdigit()
            and ent.get("remaining_count") == 2,
            f"{code} {ent}",
        )
    )
    ent_id = ent["id"] if ent else None
    verify_code = vc or None

    # VS-M6-01 / VM6-1 lookup
    code, look = req(
        "POST",
        "/shop/verifications/lookup",
        token=merchant,
        body={"mobile": mobile},
    )
    hit = next(
        (i for i in (look.get("items") or []) if i.get("entitlement_id") == ent_id),
        None,
    )
    results.append(
        check(
            "VS-M6-01/VM6-1 lookup 手机号",
            code == 200
            and look.get("result") in ("can_redeem", "multi")
            and hit is not None
            and hit.get("remaining_count") == 2,
            f"{code} {look}",
        )
    )

    code, look2 = req(
        "POST",
        "/shop/verifications/lookup",
        token=merchant,
        body={"verify_code": verify_code},
    )
    results.append(
        check(
            "VM6-1b lookup 核销码→can_redeem",
            code == 200
            and look2.get("result") == "can_redeem"
            and any(i.get("entitlement_id") == ent_id for i in (look2.get("items") or [])),
            f"{code} {look2}",
        )
    )

    # 预约
    day = (date.today() + timedelta(days=1)).isoformat()
    code, booking = req(
        "POST",
        "/mp/shop/bookings",
        token=buyer,
        body={"entitlement_id": ent_id, "booked_date": day, "booked_time_slot": "10:00-11:00"},
    )
    results.append(check("VM6-5 预约 booked", code == 200 and booking.get("status") == "booked", f"{code} {booking}"))
    booking_id = booking.get("id") if code == 200 else None

    code, conflict = req(
        "POST",
        "/mp/shop/bookings",
        token=buyer,
        body={"entitlement_id": ent_id, "booked_date": day, "booked_time_slot": "10:00-11:00"},
    )
    results.append(check("VS-M6-BOOK 时段冲突 409", code == 409, f"{code} {conflict}"))

    # 核销 execute + 幂等
    idem = f"idem-{uuid.uuid4().hex}"
    code, v1 = req(
        "POST",
        "/shop/verifications/execute",
        token=merchant,
        body={
            "entitlement_id": ent_id,
            "booking_id": booking_id,
            "deducted_count": 1,
            "idempotency_key": idem,
        },
    )
    ok_v = (
        code == 200
        and v1.get("status") == "success"
        and v1.get("remaining_count") == 1
        and v1.get("entitlement_status") == "active"
    )
    results.append(check("VS-M6-01/VM6-2 核销扣次", ok_v, f"{code} {v1}"))
    vid = v1.get("id") if code == 200 else None

    code, v2 = req(
        "POST",
        "/shop/verifications/execute",
        token=merchant,
        body={
            "entitlement_id": ent_id,
            "deducted_count": 1,
            "idempotency_key": idem,
        },
    )
    results.append(
        check(
            "VS-M6-01 幂等不双核",
            code == 200 and v2.get("id") == vid and v2.get("remaining_count") == 1,
            f"{code} {v2}",
        )
    )

    if booking_id:
        code, bl = req("GET", f"/shop/bookings/{booking_id}", token=merchant)
        results.append(
            check(
                "VM6-7 核销→预约 completed",
                code == 200 and bl.get("status") == "completed",
                f"{code} {bl}",
            )
        )
    else:
        results.append(check("VM6-7 核销→预约 completed", False, "no booking"))

    # 第二次核销耗尽
    code, v3 = req(
        "POST",
        "/shop/verifications/execute",
        token=merchant,
        body={"entitlement_id": ent_id, "deducted_count": 1, "idempotency_key": f"idem2-{uuid.uuid4().hex}"},
    )
    results.append(
        check(
            "VM6-3 次数耗尽 expired",
            code == 200 and v3.get("remaining_count") == 0 and v3.get("entitlement_status") == "expired",
            f"{code} {v3}",
        )
    )

    code, v4 = req(
        "POST",
        "/shop/verifications/execute",
        token=merchant,
        body={"entitlement_id": ent_id, "deducted_count": 1},
    )
    results.append(check("VM6-3b 耗尽后再核 409", code == 409, f"{code} {v4}"))

    # 另下一单测 revoked
    code, created2 = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    o2 = (created2 or {}).get("order") or created2
    assert code == 200, created2
    _pay_order(o2["order_no"], 9900, api_key)
    code, ents2 = req("GET", "/mp/shop/entitlements", token=buyer)
    ent2 = next((e for e in (ents2.get("items") or []) if e.get("order_id") == o2["id"]), None)
    assert ent2, ents2
    code, _ = req(
        "POST",
        f"/shop/orders/{o2['id']}/refund",
        token=merchant,
        body={"reason": "测撤销"},
    )
    code, bad = req(
        "POST",
        "/shop/verifications/execute",
        token=merchant,
        body={"entitlement_id": ent2["id"], "deducted_count": 1},
    )
    results.append(check("VS-M6-02/VM6-4 revoked 不可核销", code == 409, f"{code} {bad}"))

    # 跨店核销
    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopStore
    from uuid import UUID as UUIDType

    db = SessionLocal()
    try:
        tid = UUIDType(tenant_id)
        primary = (
            db.query(ShopStore)
            .filter(uuid_eq(ShopStore.tenant_id, tid))
            .order_by(ShopStore.created_at.asc())
            .first()
        )
        other = ShopStore(
            id=uuid.uuid4(),
            tenant_id=tid,
            merchant_id=primary.merchant_id if primary else None,
            name="M6跨店测试店",
            slug=f"m6-x-{uuid.uuid4().hex[:6]}",
            status="active",
            allow_cross_shop_redeem=False,
        )
        db.add(other)
        db.commit()
        other_id = str(other.id)
    finally:
        db.close()

    # 第三单服务权益供跨店
    code, created3 = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    o3 = (created3 or {}).get("order") or created3
    _pay_order(o3["order_no"], 9900, api_key)
    code, ents3 = req("GET", "/mp/shop/entitlements", token=buyer)
    ent3 = next((e for e in (ents3.get("items") or []) if e.get("order_id") == o3["id"]), None)
    assert ent3

    code, cross_deny = req(
        "POST",
        "/shop/verifications/execute",
        token=merchant,
        body={"entitlement_id": ent3["id"], "shop_id": other_id, "deducted_count": 1},
    )
    results.append(check("VS-M6-04 跨店未开启 409", code == 409, f"{code} {cross_deny}"))

    code, _ = req(
        "POST",
        "/shop/stores/cross-redeem",
        token=merchant,
        body={"allow_cross_shop_redeem": True, "shop_id": other_id},
    )
    code, cross_ok = req(
        "POST",
        "/shop/verifications/execute",
        token=merchant,
        body={
            "entitlement_id": ent3["id"],
            "shop_id": other_id,
            "deducted_count": 1,
            "idempotency_key": f"x-{uuid.uuid4().hex}",
        },
    )
    results.append(
        check(
            "VS-M6-04 开启跨店可核",
            code == 200 and cross_ok.get("status") == "success",
            f"{code} {cross_ok}",
        )
    )

    # 学课进度
    code, created_c = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": course_pid})
    oc = (created_c or {}).get("order") or created_c
    _pay_order(oc["order_no"], 9900, api_key)
    code, ents_c = req("GET", "/mp/shop/entitlements", token=buyer)
    ent_c = next((e for e in (ents_c.get("items") or []) if e.get("order_id") == oc["id"]), None)
    lesson_id = str(uuid.uuid4())
    course_id = str(uuid.uuid4())
    code, prog = req(
        "PUT",
        f"/mp/shop/entitlements/{ent_c['id']}/lessons/{lesson_id}/progress",
        token=buyer,
        body={"course_id": course_id, "position_sec": 120, "progress_pct": 35},
    )
    results.append(
        check(
            "VS-M6-05 学课进度可写",
            code == 200 and prog.get("position_sec") == 120 and prog.get("progress_pct") == 35,
            f"{code} {prog}",
        )
    )
    code, prog2 = req(
        "GET",
        f"/mp/shop/entitlements/{ent_c['id']}/lessons/{lesson_id}/progress",
        token=buyer,
    )
    results.append(
        check(
            "VS-M6-05 学课进度可读",
            code == 200 and prog2.get("position_sec") == 120,
            f"{code} {prog2}",
        )
    )

    # 开票
    code, inv_bad = req(
        "POST",
        "/mp/shop/invoices",
        token=buyer,
        body={
            "order_id": order_id,
            "title_type": "company",
            "title": "测试公司",
            "tax_no": "123",
            "email": "m6@example.com",
        },
    )
    results.append(check("VS-M6-03 税号校验 422", code == 422, f"{code} {inv_bad}"))

    # 用课程订单开票（仍为 paid）
    code, inv_p = req(
        "POST",
        "/mp/shop/invoices",
        token=buyer,
        body={"order_id": oc["id"], "title_type": "person", "title": "张三", "email": "zhang@example.com"},
    )
    results.append(
        check(
            "VM6-8 发票个人 submitted",
            code == 200 and inv_p.get("status") == "submitted",
            f"{code} {inv_p}",
        )
    )
    inv_p_id = inv_p.get("id") if code == 200 else None

    # 另开企业票：再下一单课程
    code, created4 = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": course_pid})
    o4 = (created4 or {}).get("order") or created4
    _pay_order(o4["order_no"], 9900, api_key)
    tax = "91110000MA01234567"
    code, inv_c = req(
        "POST",
        "/mp/shop/invoices",
        token=buyer,
        body={
            "order_id": o4["id"],
            "title_type": "company",
            "title": "北京测试有限公司",
            "tax_no": tax,
            "email": "corp@example.com",
        },
    )
    results.append(
        check(
            "VM6-9 发票企业+税号",
            code == 200 and inv_c.get("status") == "submitted" and inv_c.get("tax_no") == tax,
            f"{code} {inv_c}",
        )
    )
    inv_c_id = inv_c.get("id") if code == 200 else None

    if inv_p_id:
        inv_no = f"INV{uuid.uuid4().hex[:10].upper()}"
        code, issued = req(
            "POST",
            f"/shop/invoices/{inv_p_id}/issue",
            token=merchant,
            body={"invoice_no": inv_no, "invoice_url": "https://example.com/inv/m6.pdf"},
        )
        results.append(
            check(
                "VM6-10 发票开具(发票号码)",
                code == 200
                and issued.get("status") == "issued"
                and issued.get("invoice_no") == inv_no,
                f"{code} {issued}",
            )
        )
    else:
        results.append(check("VM6-10 发票开具(发票号码)", False, "no inv"))

    if inv_c_id:
        code, rej_short = req(
            "POST",
            f"/shop/invoices/{inv_c_id}/reject",
            token=merchant,
            body={"reason": "短"},
        )
        results.append(check("VM6-11a 驳回原因过短 422", code == 422, f"{code} {rej_short}"))
        code, rej = req(
            "POST",
            f"/shop/invoices/{inv_c_id}/reject",
            token=merchant,
            body={"reason": "抬头不符"},
        )
        results.append(
            check(
                "VM6-11 发票驳回",
                code == 200 and rej.get("status") == "rejected" and rej.get("reject_reason") == "抬头不符",
                f"{code} {rej}",
            )
        )
    else:
        results.append(check("VM6-11a 驳回原因过短 422", False, "no inv"))
        results.append(check("VM6-11 发票驳回", False, "no inv"))

    # refunded 不可申请
    code, created5 = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": course_pid})
    o5 = (created5 or {}).get("order") or created5
    _pay_order(o5["order_no"], 9900, api_key)
    code, _ = req(
        "POST",
        f"/shop/orders/{o5['id']}/refund",
        token=merchant,
        body={"reason": "测不可开票"},
    )
    code, inv_ref = req(
        "POST",
        "/mp/shop/invoices",
        token=buyer,
        body={"order_id": o5["id"], "title_type": "person", "title": "李四", "email": "li@example.com"},
    )
    results.append(check("VM6-12 refunded 不可开票 409", code == 409, f"{code} {inv_ref}"))

    # 已开票后退款 → invoice needs_red_flush
    code, created6 = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": course_pid})
    o6 = (created6 or {}).get("order") or created6
    _pay_order(o6["order_no"], 9900, api_key)
    code, inv6 = req(
        "POST",
        "/mp/shop/invoices",
        token=buyer,
        body={"order_id": o6["id"], "title_type": "person", "title": "王五", "email": "wang@example.com"},
    )
    assert code == 200, inv6
    code, issued6 = req(
        "POST",
        f"/shop/invoices/{inv6['id']}/issue",
        token=merchant,
        body={"invoice_no": f"RED{uuid.uuid4().hex[:8].upper()}"},
    )
    assert code == 200, issued6
    code, ref6 = req(
        "POST",
        f"/shop/orders/{o6['id']}/refund",
        token=merchant,
        body={"reason": "红冲测"},
    )
    code, inv_list = req("GET", "/shop/invoices?page=1&page_size=50", token=merchant)
    row6 = next((i for i in (inv_list.get("items") or []) if i.get("id") == inv6["id"]), None)
    results.append(
        check(
            "VM6-13 退款→红冲标记",
            code == 200 and row6 is not None and row6.get("needs_red_flush") is True,
            f"{code} {row6}",
        )
    )
    results.append(
        check(
            "VM6-13b 发票列表 status_counts",
            code == 200 and isinstance(inv_list.get("status_counts"), dict),
            f"{code} {inv_list.get('status_counts')}",
        )
    )
    code, inv_export = req("GET", "/shop/invoices/export", token=merchant)
    export_ok = code == 200 and (
        (isinstance(inv_export, str) and ("订单" in inv_export or "invoice" in inv_export.lower()))
        or (isinstance(inv_export, dict) and inv_export.get("detail") is None)
    )
    results.append(check("VM6-13c 发票导出 CSV", export_ok, f"{code} {str(inv_export)[:120]}"))

    # 预约取消
    code, created7 = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    o7 = (created7 or {}).get("order") or created7
    _pay_order(o7["order_no"], 9900, api_key)
    code, ents7 = req("GET", "/mp/shop/entitlements", token=buyer)
    ent7 = next((e for e in (ents7.get("items") or []) if e.get("order_id") == o7["id"]), None)
    day2 = (date.today() + timedelta(days=2)).isoformat()
    code, b7 = req(
        "POST",
        "/mp/shop/bookings",
        token=buyer,
        body={"entitlement_id": ent7["id"], "booked_date": day2, "booked_time_slot": "14:00-15:00"},
    )
    code, cancelled = req(
        "POST",
        f"/mp/shop/bookings/{b7['id']}/cancel",
        token=buyer,
        body={"reason": "改期"},
    )
    results.append(
        check("VM6-6 预约取消", code == 200 and cancelled.get("status") == "cancelled", f"{code} {cancelled}")
    )

    # shop_clerk 权限
    clerk = _ensure_clerk_token(tenant_id)
    code, look_c = req(
        "POST",
        "/shop/verifications/lookup",
        token=clerk,
        body={"mobile": mobile},
    )
    results.append(check("VM6-14 clerk 可 lookup", code == 200, f"{code} {look_c}"))
    code, prod_forbid = req("GET", "/shop/products", token=clerk)
    results.append(check("VM6-14 clerk 不可商品 403", code == 403, f"{code} {prod_forbid}"))
    code, inv_forbid = req("GET", "/shop/invoices", token=clerk)
    results.append(check("VM6-14 clerk 不可发票 403", code == 403, f"{code} {inv_forbid}"))

    # 核销记录列表
    code, vlist = req("GET", "/shop/verifications?page=1&page_size=20", token=merchant)
    results.append(
        check("VM6-4 核销记录列表", code == 200 and (vlist.get("total") or 0) >= 1, f"{code} {vlist}")
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
