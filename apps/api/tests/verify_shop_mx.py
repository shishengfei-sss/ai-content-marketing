#!/usr/bin/env python3
"""Mx Mock 首演验收（附录 B / PRD §3.5.4）+ M14 页结构断言。

真机档另签；本脚本仅 Mock 档。
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
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

    phone = "13900000099"
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
                    "tenant_name": f"Mx商户-{uuid.uuid4().hex[:6]}",
                    "display_name": "Mx测试",
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


def _ensure_on_sale_product(merchant: str) -> tuple[str, dict]:
    from tests.shop_catalog_helper import ensure_on_sale_product

    pid = ensure_on_sale_product(merchant, "course", price_cents=19900)
    code, pub = req("GET", f"/shop/products/{pid}", token=merchant)
    assert code == 200, pub
    return pid, pub


def _buyer_login(tenant_id: str, openid: str) -> str:
    code, data = req(
        "POST",
        "/mp/shop/auth/login",
        body={"tenant_id": tenant_id, "code": f"mock:{openid}"},
    )
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    from app.database import SessionLocal
    from app.models.shop import ShopSmsLog
    from app.services.shop.channel_service import stub_douyin_sign

    results: list[bool] = []

    # M14 页结构（非「文件存在」冒烟：核对 PRD 关键文案）
    claim_vue = REPO_ROOT / "apps" / "mp" / "src" / "pages" / "shop" / "claim.vue"
    text = claim_vue.read_text(encoding="utf-8") if claim_vue.is_file() else ""
    results.append(
        check(
            "MX-UI M14 领权页结构",
            "确认领取" in text
            and "链接已失效" in text
            and "领取成功" in text
            and "去已购" in text
            and "手机号与购买号不一致" in text,
            str(claim_vue),
        )
    )
    ent_vue = REPO_ROOT / "apps" / "mp" / "src" / "pages" / "shop" / "entitlements.vue"
    results.append(
        check(
            "MX-UI M06 已购落点页",
            ent_vue.is_file() and "已购内容" in ent_vue.read_text(encoding="utf-8"),
            str(ent_vue),
        )
    )

    merchant, tenant_id = _ensure_merchant_token()
    admin = login("13800000000", "admin123456")
    secret = f"mxsec_{uuid.uuid4().hex[:12]}"
    dy_shop = f"dy_mx_{uuid.uuid4().hex[:8]}"

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
        check("MX-SETUP 对接配置", code == 200 and cfg.get("douyin_configured") is True, f"{code}")
    )

    # MX-01 上架课类 SKU → on_sale
    pid, pub = _ensure_on_sale_product(merchant)
    results.append(
        check(
            "MX-01 上架课类 on_sale",
            pub.get("status") == "on_sale",
            f"{pub}",
        )
    )

    # MX-02 / MX-03 映射 + 外部审核
    ch_pid = f"dyprod_mx_{uuid.uuid4().hex[:8]}"
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
            "MX-02/03 映射挂载+外部审核",
            code == 200
            and mapping.get("status") == "mapped"
            and mapping.get("external_audit_status") in ("approved", "已通过"),
            f"{code} {mapping}",
        )
    )

    # MX-04 公域下单支付
    ext_no = f"MXO{uuid.uuid4().hex[:12]}"
    event_id = f"evt_mx_{uuid.uuid4().hex}"
    mobile = "139" + f"{uuid.uuid4().int % 10**8:08d}"
    amount = 19900
    sign = stub_douyin_sign(
        {
            "event_id": event_id,
            "external_order_no": ext_no,
            "channel_product_id": ch_pid,
            "paid_amount_cents": amount,
            "buyer_mobile": mobile,
        },
        secret,
    )
    code, wh = req(
        "POST",
        "/webhooks/douyin/order",
        body={
            "event_id": event_id,
            "external_order_no": ext_no,
            "channel_product_id": ch_pid,
            "paid_amount_cents": amount,
            "buyer_mobile": mobile,
            "douyin_shop_id": dy_shop,
            "tenant_id": tenant_id,
            "sign": sign,
        },
    )
    claim_token = wh.get("claim_token") if isinstance(wh, dict) else None
    results.append(
        check(
            "MX-04 Webhook→claim_pending",
            code == 200
            and wh.get("order_status") == "claim_pending"
            and bool(claim_token)
            and bool(wh.get("entitlement_id")),
            f"{code} {wh}",
        )
    )

    # 短信含 M14 小程序路径
    db = SessionLocal()
    try:
        sms = (
            db.query(ShopSmsLog)
            .filter(ShopSmsLog.buyer_mobile == mobile, ShopSmsLog.type == "claim_link")
            .order_by(ShopSmsLog.sent_at.desc())
            .first()
        )
        sms_ok = (
            sms is not None
            and "/pages/shop/claim" in (sms.content or "")
            and (claim_token or "") in (sms.content or "")
            and tenant_id in (sms.content or "")
        )
    finally:
        db.close()
    results.append(check("MX-05a 短信领权链接指向 M14", sms_ok, mobile))

    # MX-05 领权信息 + 绑定
    code, info = req("GET", f"/mp/shop/claim/{claim_token}")
    results.append(
        check(
            "MX-05b 领权信息 pending+tenant",
            code == 200
            and info.get("status") == "pending"
            and str(info.get("tenant_id")) == tenant_id
            and bool(info.get("mobile_masked"))
            and info.get("mobile_tail") == mobile[-4:],
            f"{code} {info}",
        )
    )

    buyer = _buyer_login(tenant_id, f"mx_{uuid.uuid4().hex[:10]}")
    # confirm_claim 会把购买手机号挂到当前 openid（与 M14「授权后确认」等价的 API 落点）
    code, claimed = req("POST", f"/mp/shop/claim/{claim_token}", token=buyer)
    code_me, me = req("GET", "/mp/shop/auth/me", token=buyer)
    results.append(
        check(
            "MX-05 领权确认 claimed_buyer",
            code == 200
            and claimed.get("status") == "claimed"
            and claimed.get("order_status") == "paid"
            and bool(claimed.get("entitlement_id"))
            and code_me == 200
            and me.get("mobile") == mobile,
            f"{code} {claimed} me={me}",
        )
    )

    # MX-06 履约：权益 active
    code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
    ent = next(
        (i for i in (ents.get("items") or []) if i.get("id") == claimed.get("entitlement_id")),
        None,
    )
    results.append(
        check(
            "MX-06 权益 active 可履约",
            code == 200 and ent is not None and ent.get("status") == "active",
            f"{code} {ent}",
        )
    )

    # MX-08 重复 Webhook 不双开（先于退款）
    sign_dup = stub_douyin_sign(
        {
            "event_id": event_id,
            "external_order_no": ext_no,
            "channel_product_id": ch_pid,
            "paid_amount_cents": amount,
            "buyer_mobile": mobile,
        },
        secret,
    )
    code, dup = req(
        "POST",
        "/webhooks/douyin/order",
        body={
            "event_id": event_id,
            "external_order_no": ext_no,
            "channel_product_id": ch_pid,
            "paid_amount_cents": amount,
            "buyer_mobile": mobile,
            "douyin_shop_id": dy_shop,
            "tenant_id": tenant_id,
            "sign": sign_dup,
        },
    )
    code2, ents2 = req("GET", "/mp/shop/entitlements", token=buyer)
    same_ent_count = sum(
        1 for i in (ents2.get("items") or []) if i.get("id") == claimed.get("entitlement_id")
    )
    results.append(
        check(
            "MX-08 重复 Webhook 不双开",
            code == 200
            and dup.get("status") in ("idempotent", "ok")
            and same_ent_count == 1,
            f"{code} {dup} count={same_ent_count}",
        )
    )

    # MX-07 退款 → revoked
    rf_event = f"evt_mx_rf_{uuid.uuid4().hex}"
    sign_rf = stub_douyin_sign(
        {
            "event_id": rf_event,
            "external_order_no": ext_no,
            "channel_product_id": "",
            "paid_amount_cents": "",
        },
        secret,
    )
    code, ref = req(
        "POST",
        "/webhooks/douyin/refund",
        body={
            "event_id": rf_event,
            "external_order_no": ext_no,
            "tenant_id": tenant_id,
            "douyin_shop_id": dy_shop,
            "reason": "Mx退款验收",
            "sign": sign_rf,
        },
    )
    code_e, ents_rf = req("GET", "/mp/shop/entitlements", token=buyer)
    ent_rf = next(
        (i for i in (ents_rf.get("items") or []) if i.get("id") == claimed.get("entitlement_id")),
        None,
    )
    results.append(
        check(
            "MX-07 退款→权益 revoked",
            code == 200
            and ref.get("order_status") == "refunded"
            and ent_rf is not None
            and ent_rf.get("status") == "revoked",
            f"{code} {ref} {ent_rf}",
        )
    )

    # 过期态可观测（附录 B 失败可观测）
    from app.services.shop.channel_service import expire_claim_token_for_test

    ext2 = f"MXE{uuid.uuid4().hex[:12]}"
    eid2 = f"evt_mx_exp_{uuid.uuid4().hex}"
    mobile2 = "138" + f"{uuid.uuid4().int % 10**8:08d}"
    sign2 = stub_douyin_sign(
        {
            "event_id": eid2,
            "external_order_no": ext2,
            "channel_product_id": ch_pid,
            "paid_amount_cents": amount,
            "buyer_mobile": mobile2,
        },
        secret,
    )
    code, wh2 = req(
        "POST",
        "/webhooks/douyin/order",
        body={
            "event_id": eid2,
            "external_order_no": ext2,
            "channel_product_id": ch_pid,
            "paid_amount_cents": amount,
            "buyer_mobile": mobile2,
            "douyin_shop_id": dy_shop,
            "tenant_id": tenant_id,
            "sign": sign2,
        },
    )
    tok2 = wh2.get("claim_token")
    db = SessionLocal()
    try:
        expire_claim_token_for_test(db, tok2)
    finally:
        db.close()
    code, info_exp = req("GET", f"/mp/shop/claim/{tok2}")
    results.append(
        check(
            "MX-OBS 领权过期态",
            code == 200 and info_exp.get("status") == "expired",
            f"{code} {info_exp}",
        )
    )

    # 挂载闸拒单审计（附录 B）
    bad_eid = f"evt_bad_{uuid.uuid4().hex}"
    bad_ext = f"BAD{uuid.uuid4().hex[:8]}"
    bad_sign = stub_douyin_sign(
        {
            "event_id": bad_eid,
            "external_order_no": bad_ext,
            "channel_product_id": "no_map_product",
            "paid_amount_cents": amount,
        },
        secret,
    )
    code, bad = req(
        "POST",
        "/webhooks/douyin/order",
        body={
            "event_id": bad_eid,
            "external_order_no": bad_ext,
            "channel_product_id": "no_map_product",
            "paid_amount_cents": amount,
            "buyer_mobile": mobile,
            "douyin_shop_id": dy_shop,
            "tenant_id": tenant_id,
            "sign": bad_sign,
        },
    )
    results.append(
        check(
            "MX-OBS 挂载闸拒单",
            code == 409 and bad.get("detail") == "mapping_not_found",
            f"{code} {bad}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total} (Mx Mock)")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
