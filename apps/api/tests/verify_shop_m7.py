#!/usr/bin/env python3
"""M7 公域链路①验收。对照执行计划 §11.2 VS-M7-01～05 + VM7 主路径。"""

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
    from app.database import SessionLocal, uuid_eq
    from app.models import TenantMembership, TenantRole, User
    from app.models.shop import ShopMerchantAccount
    from app.services.auth_service import hash_password

    phone = "13900000098"
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
                    "tenant_name": f"M7商户-{uuid.uuid4().hex[:6]}",
                    "display_name": "M7测试",
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

    return ensure_on_sale_product(merchant, "course", price_cents=19900)


def _buyer_login(tenant_id: str, openid: str) -> str:
    code, data = req(
        "POST",
        "/mp/shop/auth/login",
        body={"tenant_id": tenant_id, "code": f"mock:{openid}"},
    )
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    from app.services.shop.channel_service import stub_douyin_sign

    results: list[bool] = []

    merchant, tenant_id = _ensure_merchant_token()
    admin = login("13800000000", "admin123456")
    secret = f"m7sec_{uuid.uuid4().hex[:12]}"
    dy_shop = f"dy_{uuid.uuid4().hex[:8]}"

    # VM7-12 对接配置
    code, cfg = req(
        "POST",
        "/shop/channel-settings",
        token=merchant,
        body={
            "enabled_combos": ["1A"],
            "douyin_shop_id": dy_shop,
            "douyin_webhook_secret": secret,
        },
    )
    results.append(
        check(
            "VM7-12 对接配置保存",
            code == 200 and cfg.get("douyin_configured") is True,
            f"{code} {cfg}",
        )
    )

    pid = _ensure_on_sale_product(merchant)
    ch_pid = f"dyprod_{uuid.uuid4().hex[:8]}"

    # VM7-1 正常映射
    code, mapping = req(
        "POST",
        "/shop/channel-mappings",
        token=merchant,
        body={
            "product_id": pid,
            "channel": "douyin",
            "channel_product_id": ch_pid,
            "combo": "1A",
        },
    )
    results.append(
        check(
            "VM7-1/VS-M7-01 映射成功",
            code == 200
            and mapping.get("status") == "mapped"
            and mapping.get("channel_label") == "抖店"
            and mapping.get("status_label") == "已挂载",
            f"{code} {mapping}",
        )
    )
    mapping_id = mapping.get("id") if code == 200 else None

    code, mlist = req("GET", "/shop/channel-mappings?page=1&page_size=20", token=merchant)
    results.append(
        check(
            "VM7-1b 映射列表中文标签+status_counts",
            code == 200
            and isinstance(mlist.get("status_counts"), dict)
            and any(
                i.get("id") == mapping_id and i.get("channel_label") == "抖店"
                for i in (mlist.get("items") or [])
            ),
            f"{code} {mlist}",
        )
    )

    # off_sale 不可映射
    code, draft = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={"type": "digital", "name": f"M7-off-{uuid.uuid4().hex[:4]}", "price_cents": 100},
    )
    assert code == 200, draft
    code, bad_map = req(
        "POST",
        "/shop/channel-mappings",
        token=merchant,
        body={
            "product_id": draft["id"],
            "channel_product_id": f"bad_{uuid.uuid4().hex[:6]}",
            "combo": "1A",
        },
    )
    results.append(
        check(
            "VM7-2/VS-M7-01 off_sale 拒绝",
            code == 409 and (bad_map.get("detail") == "product_not_on_sale"),
            f"{code} {bad_map}",
        )
    )

    # 未开通组合
    code, bad_combo = req(
        "POST",
        "/shop/channel-mappings",
        token=merchant,
        body={
            "product_id": pid,
            "channel_product_id": f"combo_{uuid.uuid4().hex[:6]}",
            "combo": "2A",
        },
    )
    results.append(
        check(
            "VS-M7-05 channel_combo_not_enabled",
            code == 422 and bad_combo.get("detail") == "channel_combo_not_enabled",
            f"{code} {bad_combo}",
        )
    )

    # Webhook 下单
    ext_no = f"DYO{uuid.uuid4().hex[:12]}"
    event_id = f"evt_{uuid.uuid4().hex}"
    mobile = "139" + f"{uuid.uuid4().int % 10**8:08d}"
    amount = 19900
    sign = stub_douyin_sign(
        {
            "event_id": event_id,
            "external_order_no": ext_no,
            "channel_product_id": ch_pid,
            "paid_amount_cents": amount,
        },
        secret,
    )
    code, wh = req(
        "POST",
        "/webhooks/douyin/order",
        body={
            "event_id": event_id,
            "event_type": "order.paid",
            "tenant_id": tenant_id,
            "douyin_shop_id": dy_shop,
            "channel_product_id": ch_pid,
            "external_order_no": ext_no,
            "buyer_mobile": mobile,
            "paid_amount_cents": amount,
            "sign": sign,
            "combo": "1A",
        },
    )
    results.append(
        check(
            "VM7-4/VS-M7-02 Webhook→claim_pending+权益",
            code == 200
            and wh.get("order_status") == "claim_pending"
            and bool(wh.get("claim_token"))
            and bool(wh.get("entitlement_id")),
            f"{code} {wh}",
        )
    )
    token = wh.get("claim_token")
    order_id = wh.get("order_id")

    # 幂等
    code, wh2 = req(
        "POST",
        "/webhooks/douyin/order",
        body={
            "event_id": event_id,
            "event_type": "order.paid",
            "tenant_id": tenant_id,
            "channel_product_id": ch_pid,
            "external_order_no": ext_no,
            "buyer_mobile": mobile,
            "paid_amount_cents": amount,
            "sign": sign,
            "combo": "1A",
        },
    )
    results.append(
        check(
            "VM7-9 Webhook 幂等",
            code == 200 and wh2.get("status") == "idempotent" and wh2.get("order_id") == order_id,
            f"{code} {wh2}",
        )
    )

    # 拒单审计（无映射）
    ext_bad = f"DYBAD{uuid.uuid4().hex[:10]}"
    eid_bad = f"evt_bad_{uuid.uuid4().hex}"
    sign_bad = stub_douyin_sign(
        {
            "event_id": eid_bad,
            "external_order_no": ext_bad,
            "channel_product_id": "no_such_product",
            "paid_amount_cents": amount,
        },
        secret,
    )
    code, rej = req(
        "POST",
        "/webhooks/douyin/order",
        body={
            "event_id": eid_bad,
            "tenant_id": tenant_id,
            "channel_product_id": "no_such_product",
            "external_order_no": ext_bad,
            "buyer_mobile": mobile,
            "paid_amount_cents": amount,
            "sign": sign_bad,
            "combo": "1A",
        },
    )
    results.append(check("VS-M7-04 拒单 409", code == 409, f"{code} {rej}"))
    code, audit = req(
        "GET",
        f"/shop/channel-mappings/audit?external_order_id={ext_bad}",
        token=merchant,
    )
    results.append(
        check(
            "VS-M7-04 审计可查 external_order_id",
            code == 200
            and any(
                (i.get("detail_json") or {}).get("external_order_id") == ext_bad
                for i in (audit.get("items") or [])
            ),
            f"{code} {audit}",
        )
    )

    # 领权
    code, info = req("GET", f"/mp/shop/claim/{token}")
    results.append(
        check(
            "VM7-5 领权信息 pending",
            code == 200 and info.get("status") == "pending" and info.get("mobile_tail") == mobile[-4:],
            f"{code} {info}",
        )
    )

    buyer = _buyer_login(tenant_id, f"m7_{uuid.uuid4().hex[:10]}")
    code, claimed = req("POST", f"/mp/shop/claim/{token}", token=buyer)
    results.append(
        check(
            "VM7-6 领权确认 paid",
            code == 200
            and claimed.get("status") == "claimed"
            and claimed.get("order_status") == "paid"
            and bool(claimed.get("entitlement_id")),
            f"{code} {claimed}",
        )
    )

    code, again = req("POST", f"/mp/shop/claim/{token}", token=buyer)
    results.append(
        check(
            "VM7-7 已领再确认 claimed",
            code == 200 and again.get("status") == "claimed",
            f"{code} {again}",
        )
    )

    # 过期 token
    from app.database import SessionLocal
    from app.services.shop.channel_service import expire_claim_token_for_test

    # 再下一单测过期
    ext2 = f"DYO{uuid.uuid4().hex[:12]}"
    eid2 = f"evt_{uuid.uuid4().hex}"
    sign2 = stub_douyin_sign(
        {
            "event_id": eid2,
            "external_order_no": ext2,
            "channel_product_id": ch_pid,
            "paid_amount_cents": amount,
        },
        secret,
    )
    code, wh3 = req(
        "POST",
        "/webhooks/douyin/order",
        body={
            "event_id": eid2,
            "tenant_id": tenant_id,
            "channel_product_id": ch_pid,
            "external_order_no": ext2,
            "buyer_mobile": "138" + f"{uuid.uuid4().int % 10**8:08d}",
            "paid_amount_cents": amount,
            "sign": sign2,
            "combo": "1A",
        },
    )
    token_exp = wh3.get("claim_token")
    db = SessionLocal()
    try:
        expire_claim_token_for_test(db, token_exp)
    finally:
        db.close()
    code, exp = req("POST", f"/mp/shop/claim/{token_exp}", token=buyer)
    results.append(
        check("VM7-8/VS-M7-03 领权过期 410", code == 410, f"{code} {exp}")
    )

    # 退款 webhook
    eid_rf = f"evt_rf_{uuid.uuid4().hex}"
    sign_rf = stub_douyin_sign(
        {
            "event_id": eid_rf,
            "external_order_no": ext_no,
            "channel_product_id": "",
            "paid_amount_cents": "",
        },
        secret,
    )
    code, rf = req(
        "POST",
        "/webhooks/douyin/refund",
        body={
            "event_id": eid_rf,
            "tenant_id": tenant_id,
            "external_order_no": ext_no,
            "reason": "抖店退款验收",
            "sign": sign_rf,
        },
    )
    results.append(
        check(
            "VM7-10 抖店退款",
            code == 200 and rf.get("order_status") == "refunded",
            f"{code} {rf}",
        )
    )
    if claimed.get("entitlement_id"):
        code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
        e = next(
            (i for i in (ents.get("items") or []) if i.get("id") == claimed["entitlement_id"]),
            None,
        )
        results.append(
            check(
                "VM7-10 权益 revoked",
                e is not None and e.get("status") == "revoked",
                f"{code} {e}",
            )
        )
    else:
        results.append(check("VM7-10 权益 revoked", False, "no ent"))

    # 强制下架
    if mapping_id:
        code, fu = req(
            "POST",
            f"/admin/shop/channel-mappings/{mapping_id}/force-unmount",
            token=admin,
        )
        results.append(
            check("VM7-11 强制下架", code == 200 and fu.get("status") == "unmapped", f"{code} {fu}")
        )
    else:
        results.append(check("VM7-11 强制下架", False, "no mapping"))

    # suspended 商家不可映射（临时改状态）
    from app.database import uuid_eq
    from app.models.shop import ShopMerchantAccount
    from uuid import UUID as UUIDType

    db = SessionLocal()
    try:
        m = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.tenant_id, UUIDType(tenant_id)))
            .first()
        )
        old = m.status
        m.status = "suspended"
        db.commit()
    finally:
        db.close()
    code, sus = req(
        "POST",
        "/shop/channel-mappings",
        token=merchant,
        body={
            "product_id": pid,
            "channel_product_id": f"sus_{uuid.uuid4().hex[:6]}",
            "combo": "1A",
        },
    )
    results.append(
        check(
            "VM7-3 suspended 不可映射",
            code == 409 and sus.get("detail") == "merchant_not_active",
            f"{code} {sus}",
        )
    )
    db = SessionLocal()
    try:
        m = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.tenant_id, UUIDType(tenant_id)))
            .first()
        )
        m.status = old
        db.commit()
    finally:
        db.close()

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
