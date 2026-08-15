#!/usr/bin/env python3
"""买家履约页（M06–M13）结构断言 + API 联调。

对照 PRD 02-买家端UI.html #m06 #m07 #m08 #m09 #m10 #m13。
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402

SHOP = REPO_ROOT / "apps" / "mp" / "src" / "pages" / "shop"


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def _page_has(name: str, *needles: str) -> bool:
    p = SHOP / name
    if not p.is_file():
        return False
    text = p.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _ensure_merchant() -> tuple[str, str]:
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
                    "tenant_name": f"MP履约-{uuid.uuid4().hex[:6]}",
                    "display_name": "MP履约",
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
        user.tenant_id = merchant.tenant_id
        user.hashed_password = hash_password(password)
        db.commit()
        tid = str(merchant.tenant_id)
    finally:
        db.close()
    return login(phone, password), tid


def _pay_order(order_no: str, amount: int, api_key: str) -> None:
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


def main() -> int:
    results: list[bool] = []

    results.append(
        check(
            "MP-UI M06 已购",
            _page_has("entitlements.vue", "已购", "继续学", "预约", "权限已关闭", "权益已过期"),
            "entitlements.vue",
        )
    )
    results.append(
        check(
            "MP-UI M10 预约",
            _page_has("booking.vue", "确认预约", "获取核销码", "请选择时段"),
            "booking.vue",
        )
    )
    results.append(
        check(
            "MP-UI M10b 核销码",
            _page_has("verify-code.vue", "核销码", "已复制", "预约成功"),
            "verify-code.vue",
        )
    )
    results.append(
        check(
            "MP-UI M10c 预约列表",
            _page_has("bookings.vue", "我的预约", "取消预约", "确认取消本次预约", "已取消 · 过期未核销"),
            "bookings.vue",
        )
    )
    results.append(
        check(
            "MP-UI M13 开票",
            _page_has("invoice.vue", "申请开票", "税号", "个人", "企业", "提交"),
            "invoice.vue",
        )
    )
    results.append(
        check(
            "MP-UI M07 课时目录",
            _page_has("learn.vue", "学习进度", "试看", "购买后可学习"),
            "learn.vue",
        )
    )
    results.append(
        check(
            "MP-UI M08 播放器",
            _page_has("player.vue", "试看已结束", "播放", "返回目录"),
            "player.vue",
        )
    )
    results.append(
        check(
            "MP-UI M09 资料领取",
            _page_has("materials.vue", "资料领取", "预览", "下载", "已达下载上限"),
            "materials.vue",
        )
    )

    merchant, tenant_id = _ensure_merchant()
    api_key = "mock_api_key_mp_fulfill"
    code, cfg = req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_mpf",
            "wx_app_id": "wx_mock_appid_mpf",
            "wx_api_key": api_key,
            "wx_notify_url": "http://127.0.0.1:8003/api/v1/mp/shop/payments/notify",
        },
    )
    assert code == 200, cfg

    from tests.shop_catalog_helper import ensure_on_sale_product

    pid = ensure_on_sale_product(
        merchant, "service", price_cents=9900, extra={"service_times": 2, "refund_policy": "always_allow"}
    )
    cpid = ensure_on_sale_product(merchant, "course", price_cents=9900)

    buyer_code, buyer_data = req(
        "POST",
        "/mp/shop/auth/login",
        body={"tenant_id": tenant_id, "code": f"mock:mpf_{uuid.uuid4().hex[:8]}"},
    )
    assert buyer_code == 200, buyer_data
    buyer = buyer_data["access_token"]
    mobile = "137" + f"{uuid.uuid4().int % 10**8:08d}"
    code, _ = req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})
    results.append(check("MP-API 绑定手机", code == 200, f"{code}"))

    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created or {}).get("order") or created
    assert code == 200, created
    _pay_order(order["order_no"], 9900, api_key)

    code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
    ent = next((e for e in (ents.get("items") or []) if e.get("order_id") == order["id"]), None)
    results.append(
        check(
            "MP-API M06 权益列表",
            code == 200 and ent is not None and ent.get("status") == "active" and bool(ent.get("verify_code")),
            f"{code} {ent}",
        )
    )

    day = (date.today() + timedelta(days=1)).isoformat()
    code, booking = req(
        "POST",
        "/mp/shop/bookings",
        token=buyer,
        body={"entitlement_id": ent["id"], "booked_date": day, "booked_time_slot": "10:00-11:00"},
    )
    results.append(
        check("MP-API M10 预约", code == 200 and booking.get("status") == "booked", f"{code} {booking}")
    )

    code, blist = req("GET", "/mp/shop/bookings?page=1&page_size=20", token=buyer)
    results.append(
        check(
            "MP-API M10c 预约列表",
            code == 200 and any(i.get("id") == booking.get("id") for i in (blist.get("items") or [])),
            f"{code}",
        )
    )

    code, cancelled = req(
        "POST",
        f"/mp/shop/bookings/{booking['id']}/cancel",
        token=buyer,
        body={"reason": "buyer_cancel"},
    )
    results.append(
        check(
            "MP-API M10 取消预约",
            code == 200 and cancelled.get("status") == "cancelled",
            f"{code} {cancelled}",
        )
    )

    # 课程：目录 + 进度 + 开票
    code, created2 = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": cpid})
    o2 = (created2 or {}).get("order") or created2
    assert code == 200, created2
    _pay_order(o2["order_no"], 9900, api_key)

    code, ents2 = req("GET", "/mp/shop/entitlements", token=buyer)
    ent_c = next((e for e in (ents2.get("items") or []) if e.get("order_id") == o2["id"]), None)
    assert ent_c, ents2
    code, outline = req("GET", f"/mp/shop/entitlements/{ent_c['id']}/outline", token=buyer)
    results.append(
        check(
            "MP-API M07 课时目录",
            code == 200
            and (outline.get("total_count") or 0) >= 1
            and bool(outline.get("lessons")),
            f"{code} {outline}",
        )
    )
    lesson0 = (outline.get("lessons") or [None])[0]
    if lesson0:
        code, prog = req(
            "PUT",
            f"/mp/shop/entitlements/{ent_c['id']}/lessons/{lesson0['id']}/progress",
            token=buyer,
            body={
                "course_id": outline.get("course_id"),
                "position_sec": 90,
                "progress_pct": 20,
            },
        )
        results.append(
            check(
                "MP-API M08 进度上报",
                code == 200 and prog.get("position_sec") == 90,
                f"{code} {prog}",
            )
        )
    else:
        results.append(check("MP-API M08 进度上报", False, "no lesson"))

    code, inv = req(
        "POST",
        "/mp/shop/invoices",
        token=buyer,
        body={
            "order_id": o2["id"],
            "title_type": "person",
            "title": "测试买家",
            "email": "buyer@example.com",
        },
    )
    results.append(
        check(
            "MP-API M13 申请开票",
            code == 200 and inv.get("status") == "submitted",
            f"{code} {inv}",
        )
    )

    code, ilist = req("GET", "/mp/shop/invoices?page=1&page_size=20", token=buyer)
    results.append(
        check(
            "MP-API M13 发票列表",
            code == 200 and any(i.get("id") == inv.get("id") for i in (ilist.get("items") or [])),
            f"{code}",
        )
    )

    # 资料包
    dpid = ensure_on_sale_product(merchant, "digital", price_cents=4900)

    code, created3 = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": dpid})
    o3 = (created3 or {}).get("order") or created3
    assert code == 200, created3
    _pay_order(o3["order_no"], 4900, api_key)
    code, ents3 = req("GET", "/mp/shop/entitlements", token=buyer)
    ent_d = next((e for e in (ents3.get("items") or []) if e.get("order_id") == o3["id"]), None)
    assert ent_d, ents3
    code, mats = req("GET", f"/mp/shop/entitlements/{ent_d['id']}/materials", token=buyer)
    files = mats.get("files") or []
    results.append(
        check(
            "MP-API M09 资料列表",
            code == 200 and len(files) >= 1,
            f"{code} {mats}",
        )
    )
    if files:
        fid = files[0]["id"]
        code, dl = req(
            "POST",
            f"/mp/shop/entitlements/{ent_d['id']}/materials/{fid}/download",
            token=buyer,
        )
        results.append(
            check(
                "MP-API M09 下载计数",
                code == 200 and dl.get("download_count") == 1 and bool(dl.get("download_url")),
                f"{code} {dl}",
            )
        )
    else:
        results.append(check("MP-API M09 下载计数", False, "no file"))

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
