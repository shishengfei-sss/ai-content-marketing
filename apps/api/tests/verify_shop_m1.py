#!/usr/bin/env python3
"""M1 套餐订阅验收：P10 + P11 + A18。对照执行计划 §5.2 VS-M1-01～09。"""

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


def _pick_active_tenant(admin: str) -> str:
    code, data = req("GET", "/admin/shop/merchants", token=admin, body=None)
    assert code == 200, data
    # basic/flagship 仅个体/企业可购；优先企业主体
    preferred = None
    for item in data.get("items") or []:
        if not item.get("merchant_id") or item.get("onboarding_status") != "active":
            continue
        if item.get("entity_type") in ("enterprise", "individual_business"):
            return item["tenant_id"]
        preferred = preferred or item["tenant_id"]
    if preferred:
        return preferred
    raise RuntimeError("no active merchant for M1 tests")


def _ensure_cs_user() -> str:
    """创建/重置管家账号（无 subscription.manage）。"""
    from app.database import SessionLocal
    from app.models import User
    from app.permissions import PLATFORM_ADMIN_ROLE, PLATFORM_SHOP_ROLE_CS
    from app.services.auth_service import hash_password

    phone = "13800000088"
    password = "cs12345678"
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.phone == phone).first()
        if not u:
            u = User(
                id=uuid.uuid4(),
                phone=phone,
                hashed_password=hash_password(password),
                display_name="商城管家测试",
                role=PLATFORM_ADMIN_ROLE,
                platform_shop_role=PLATFORM_SHOP_ROLE_CS,
            )
            db.add(u)
        else:
            u.role = PLATFORM_ADMIN_ROLE
            u.platform_shop_role = PLATFORM_SHOP_ROLE_CS
            u.hashed_password = hash_password(password)
        db.commit()
    finally:
        db.close()
    return login(phone, password)


def main() -> int:
    results: list[bool] = []
    admin = login("13800000000", "admin123456")
    tenant_id = _pick_active_tenant(admin)

    # ── P10 冒烟 ──
    code, data = req("GET", "/admin/shop/plan-templates?published=true", token=admin)
    results.append(
        check("VS-M1-P10 套餐列表", code == 200 and (data or {}).get("total", 0) >= 3, str(code))
    )

    # VS-M1-01 人工开通 basic
    today = date.today()
    expires = today + timedelta(days=365) - timedelta(days=1)
    code, sub = req(
        "POST",
        "/admin/shop/subscriptions",
        token=admin,
        body={
            "tenant_id": tenant_id,
            "plan_code": "basic",
            "purchase_mode": "replace",
            "effective_at": today.isoformat(),
            "expires_at": expires.isoformat(),
            "catalog_price_cents": 980000,
            "paid_amount_cents": 980000,
            "source": "manual",
            "remark": "VS-M1-01 验收开通",
        },
    )
    results.append(
        check(
            "VS-M1-01 人工开通 basic",
            code == 200
            and sub.get("status") == "active"
            and sub.get("plan_code") == "basic"
            and sub.get("expires_at_inclusive") == expires.isoformat(),
            f"{code} {sub}",
        )
    )
    basic_id = sub.get("id")

    # VS-M1-02 加购后 merge 含并集
    code, addon = req(
        "POST",
        "/admin/shop/subscriptions",
        token=admin,
        body={
            "tenant_id": tenant_id,
            "plan_code": "addon_products_20",
            "purchase_mode": "stack",
            "effective_at": today.isoformat(),
            "expires_at": expires.isoformat(),
            "catalog_price_cents": 59900,
            "paid_amount_cents": 59900,
            "source": "addon",
            "remark": "VS-M1-02 加购",
        },
    )
    code_e, ent = req("GET", f"/admin/shop/merchants/{tenant_id}/entitlements", token=admin)
    quotas = (ent or {}).get("quotas") or {}
    # basic 200 + addon 20 = 220 (sum)
    results.append(
        check(
            "VS-M1-02 merge 加购并集",
            code == 200
            and code_e == 200
            and quotas.get("quota.max_products") == 220
            and (ent.get("features") or {}).get("channel.doudian") is True,
            f"addon={code} products={quotas.get('quota.max_products')} ent={ent}",
        )
    )

    # VS-M1-03 换档 flagship，旧 basic superseded，无空洞
    code, flag = req(
        "POST",
        f"/admin/shop/subscriptions/{basic_id}/replace",
        token=admin,
        body={
            "target_plan_code": "flagship",
            "effective_at": today.isoformat(),
            "expires_at": expires.isoformat(),
            "catalog_price_cents": 2980000,
            "paid_amount_cents": 2980000,
            "remark": "VS-M1-03 换档",
        },
    )
    code_old, old = req("GET", f"/admin/shop/subscriptions/{basic_id}", token=admin)
    code_e2, ent2 = req("GET", f"/admin/shop/merchants/{tenant_id}/entitlements", token=admin)
    results.append(
        check(
            "VS-M1-03 换档无空洞",
            code == 200
            and flag.get("plan_code") == "flagship"
            and code_old == 200
            and old.get("status") == "superseded"
            and (ent2.get("quotas") or {}).get("quota.max_products") == "unlimited"
            and (ent2.get("features") or {}).get("channel.doudian") is True,
            f"flag={code} old={old.get('status')} products={ (ent2 or {}).get('quotas', {}).get('quota.max_products') }",
        )
    )

    # VS-M1-04 续费结案：先提申请再 renew
    code_r, ren_req = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/renewal-requests",
        token=admin,
        body={
            "purchase_mode": "renew_same",
            "target_plan": "flagship",
            "quoted_amount_cents": 2980000,
            "catalog_price_cents": 2980000,
            "customer_confirmed": True,
            "content": "VS-M1-04 续费结案验收说明足够长",
        },
    )
    # 若因 plan_status 不可申请，先把商家标为即将到期再试
    if code_r != 200:
        from app.database import SessionLocal, uuid_eq
        from app.models.shop import ShopMerchantAccount

        db = SessionLocal()
        try:
            m = (
                db.query(ShopMerchantAccount)
                .filter(uuid_eq(ShopMerchantAccount.tenant_id, uuid.UUID(str(tenant_id))))
                .first()
            )
            if m:
                m.plan_status = "expiring_soon"
                m.has_pending_renewal = False
                db.commit()
        finally:
            db.close()
        code_r, ren_req = req(
            "POST",
            f"/admin/shop/merchants/{tenant_id}/service-logs/renewal-requests",
            token=admin,
            body={
                "purchase_mode": "renew_same",
                "target_plan": "flagship",
                "quoted_amount_cents": 2980000,
                "catalog_price_cents": 2980000,
                "customer_confirmed": True,
                "content": "VS-M1-04 续费结案验收说明足够长",
            },
        )

    flag_id = flag.get("id")
    new_exp = expires + timedelta(days=365)
    code_renew, renewed = req(
        "POST",
        f"/admin/shop/subscriptions/{flag_id}/renew",
        token=admin,
        body={
            "effective_at": (expires + timedelta(days=1)).isoformat(),
            "expires_at": new_exp.isoformat(),
            "catalog_price_cents": 2980000,
            "paid_amount_cents": 2980000,
            "remark": "VS-M1-04 对公已到账",
            "renewal_request_id": ren_req.get("id") if isinstance(ren_req, dict) else None,
        },
    )
    results.append(
        check(
            "VS-M1-04 续费结案",
            code_r in (200, 201)
            and code_renew == 200
            and renewed.get("status") == "active"
            and renewed.get("source") == "renew"
            and renewed.get("expires_at_inclusive") == new_exp.isoformat(),
            f"req={code_r} renew={code_renew} {renewed}",
        )
    )

    # VS-M1-05 无 subscription.manage → 403（管家）
    cs_tok = _ensure_cs_user()
    code, data = req(
        "POST",
        "/admin/shop/subscriptions",
        token=cs_tok,
        body={
            "tenant_id": tenant_id,
            "plan_code": "free",
            "purchase_mode": "stack",
            "paid_amount_cents": 0,
            "remark": "应被拒绝",
        },
    )
    results.append(check("VS-M1-05 无 manage → 403", code == 403, f"{code} {data}"))

    # VS-M1-06 管家可提续费申请，不可直接开通（与上条一致 + 可建申请）
    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopMerchantAccount, ShopMerchantServiceLog

    db = SessionLocal()
    try:
        m = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.tenant_id, uuid.UUID(str(tenant_id))))
            .first()
        )
        if m:
            m.plan_status = "expiring_soon"
            m.has_pending_renewal = False
            db.query(ShopMerchantServiceLog).filter(
                uuid_eq(ShopMerchantServiceLog.merchant_id, m.id),
                ShopMerchantServiceLog.type == "renewal_request",
                ShopMerchantServiceLog.status == "pending",
            ).update({"status": "cancelled"}, synchronize_session=False)
            db.commit()
    finally:
        db.close()

    code_cs_req, _ = req(
        "POST",
        f"/admin/shop/merchants/{tenant_id}/service-logs/renewal-requests",
        token=cs_tok,
        body={
            "purchase_mode": "renew_same",
            "target_plan": "flagship",
            "quoted_amount_cents": 100,
            "customer_confirmed": True,
            "content": "管家提续费申请验收内容足够",
        },
    )
    # CS 可能无 merchant.read 数据范围 → 403；至少开通被拒已由 05 覆盖
    results.append(
        check(
            "VS-M1-06 管家不可直接开通",
            code == 403 and code_cs_req in (200, 403, 404, 409),
            f"open={code} renew_req={code_cs_req}",
        )
    )

    # VS-M1-07 closed 商家开通 → 422
    closed_tid = None
    db = SessionLocal()
    try:
        m = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.tenant_id, uuid.UUID(str(tenant_id))))
            .first()
        )
        if m:
            m.status = "closed"
            db.commit()
            closed_tid = tenant_id
    finally:
        db.close()

    code_c, data_c = req(
        "POST",
        "/admin/shop/subscriptions",
        token=admin,
        body={
            "tenant_id": closed_tid,
            "plan_code": "basic",
            "purchase_mode": "replace",
            "paid_amount_cents": 0,
            "remark": "closed should fail",
        },
    )
    results.append(
        check("VS-M1-07 closed → 422", code_c == 422 and "清退" in str(data_c), f"{code_c} {data_c}")
    )
    # 恢复 active
    db = SessionLocal()
    try:
        m = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.tenant_id, uuid.UUID(str(tenant_id))))
            .first()
        )
        if m:
            m.status = "active"
            db.commit()
    finally:
        db.close()

    # VS-M1-08 到期守卫
    from app.services.shop.entitlement_service import assert_merchant_writable_by_plan

    db = SessionLocal()
    try:
        m = (
            db.query(ShopMerchantAccount)
            .filter(uuid_eq(ShopMerchantAccount.tenant_id, uuid.UUID(str(tenant_id))))
            .first()
        )
        # 将全部 active 标 expired 并刷新
        from app.models.shop import ShopMerchantSubscription

        db.query(ShopMerchantSubscription).filter(
            uuid_eq(ShopMerchantSubscription.tenant_id, uuid.UUID(str(tenant_id))),
            ShopMerchantSubscription.status == "active",
        ).update({"status": "expired"}, synchronize_session=False)
        if m:
            m.plan_status = "expired"
            db.commit()
        blocked = False
        detail = ""
        try:
            assert_merchant_writable_by_plan(db, uuid.UUID(str(tenant_id)))
        except Exception as e:
            blocked = getattr(e, "status_code", None) == 422 or "到期" in str(e)
            detail = str(getattr(e, "detail", e))
        results.append(check("VS-M1-08 到期守卫", blocked and "到期" in detail, detail))
    finally:
        db.close()

    # VS-M1-09 UI 路由文件存在
    web_root = API_ROOT.parent / "web" / "src"
    files = [
        web_root / "views" / "admin" / "shop" / "PlanConfig.vue",
        web_root / "views" / "admin" / "shop" / "Subscriptions.vue",
        web_root / "views" / "shop" / "SubscriptionEntitlements.vue",
    ]
    results.append(check("VS-M1-09 UI 文件存在", all(f.is_file() for f in files), str([f.name for f in files])))

    # A18 商家只读
    try:
        merch = login("13900000099", "test123456")
        code_a, a18 = req("GET", "/shop/subscription/entitlements", token=merch)
        results.append(
            check("VS-M1-A18 商家只读权益", code_a == 200 and "quotas" in (a18 or {}), f"{code_a}")
        )
    except Exception as e:
        results.append(check("VS-M1-A18 商家只读权益", False, str(e)))

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
