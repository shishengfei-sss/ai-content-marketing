#!/usr/bin/env python3
"""A10 订单详情验收。对照 PRD 01-管理端UI.html #a10。"""

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

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop"


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _ensure_merchant() -> tuple[str, str]:
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
                    "tenant_name": f"A10验-{uuid.uuid4().hex[:6]}",
                    "display_name": "A10验",
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
        tid = str(merchant.tenant_id)
    finally:
        db.close()
    return login(phone, password), tid


def _ensure_payment(merchant: str) -> str:
    api_key = "mock_api_key_a10"
    code, data = req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_a10",
            "wx_app_id": "wx_mock_appid_a10",
            "wx_api_key": api_key,
            "wx_notify_url": "http://127.0.0.1:8003/api/v1/mp/shop/payments/notify",
        },
    )
    assert code == 200, data
    return api_key


def _pay(order_no: str, amount: int, api_key: str):
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
            "UI A10 详情栏位",
            _page_has(
                WEB / "OrderDetail.vue",
                "订单状态",
                "权益状态",
                "开票状态",
                "支付渠道",
                "商品信息",
                "买家与领权",
                "订单轨迹",
                "关闭订单",
                "退款",
                "重发短信",
                "查看开票",
                "reveal-sensitive",
            ),
        )
    )
    results.append(
        check(
            "UI A09 进 A10",
            _page_has(WEB / "OrdersList.vue", "ShopOrderDetail"),
        )
    )

    merchant, tenant_id = _ensure_merchant()
    api_key = _ensure_payment(merchant)

    # 准备在售商品（DB 强制 on_sale，避免审核链路）
    code, col = req(
        "POST", "/shop/columns", token=merchant, body={"title": f"A10专栏-{uuid.uuid4().hex[:6]}"}
    )
    from tests.http_client import _get_test_client

    client = _get_test_client()
    r = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {merchant}"},
        files={"file": ("a10.mp4", b"vid", "video/mp4")},
    )
    media = r.json()
    code, les = req(
        "POST",
        f"/shop/columns/{col['id']}/lessons",
        token=merchant,
        body={
            "title": "A10课",
            "media_type": "video",
            "media_id": media["file_id"],
            "media_url": media["file_url"],
            "duration_sec": 60,
        },
    )
    req("POST", f"/shop/columns/{col['id']}/lessons/{les['id']}/publish", token=merchant)
    req("POST", f"/shop/columns/{col['id']}/publish", token=merchant)
    cover_r = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {merchant}"},
        files={"file": ("c.png", b"\x89PNG", "image/png")},
    )
    cover = cover_r.json()["file_url"]
    code, product = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "course",
            "name": f"A10课-{uuid.uuid4().hex[:6]}",
            "price_cents": 19900,
            "cover_url": cover,
            "ref_type": "column",
            "ref_id": col["id"],
        },
    )
    results.append(check("VA10-0 建商品", code == 200, f"{code} {product}"))
    pid = product["id"]
    from uuid import UUID as UUIDType

    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopProduct

    db = SessionLocal()
    try:
        p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, UUIDType(pid))).first()
        p.status = "on_sale"
        db.commit()
    finally:
        db.close()

    openid = f"a10_{uuid.uuid4().hex[:10]}"
    code, buyer_login = req(
        "POST", "/mp/shop/auth/login", body={"tenant_id": tenant_id, "code": f"mock:{openid}"}
    )
    buyer = buyer_login["access_token"]
    mobile = "138" + f"{uuid.uuid4().int % 10**8:08d}"
    req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})
    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created or {}).get("order") or created
    results.append(check("VA10-1 下单", code == 200, f"{code} {created}"))
    oid = order["id"]
    _pay(order["order_no"], int(order["amount_cents"]), api_key)

    code, detail = req("GET", f"/shop/orders/{oid}", token=merchant)
    results.append(
        check(
            "VA10-2 详情含轨迹与权益",
            code == 200
            and detail.get("status") == "paid"
            and detail.get("entitlement_id")
            and detail.get("entitlement_status") == "active"
            and detail.get("claim_status") == "claimed"
            and isinstance(detail.get("timeline"), list)
            and len(detail.get("timeline") or []) >= 2
            and any("支付成功" in (t.get("event") or "") for t in detail["timeline"]),
            f"{code} {detail}",
        )
    )

    code, rev = req("POST", f"/shop/orders/{oid}/reveal-sensitive", token=merchant)
    results.append(
        check(
            "VA10-3 揭密别名",
            code == 200 and rev.get("buyer_mobile") == mobile,
            f"{code} {rev}",
        )
    )

    # 待付款关单
    code, o2 = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    pending = (o2 or {}).get("order") or o2
    code, closed = req(
        "POST",
        f"/shop/orders/{pending['id']}/close",
        token=merchant,
        body={"reason": "测试关闭"},
    )
    results.append(check("VA10-4 关闭待付款", code == 200 and closed.get("status") == "closed", f"{code} {closed}"))

    code, d2 = req("GET", f"/shop/orders/{pending['id']}", token=merchant)
    results.append(
        check(
            "VA10-5 关闭轨迹",
            code == 200 and any("关闭" in (t.get("event") or "") for t in (d2.get("timeline") or [])),
            f"{code} {d2.get('timeline')}",
        )
    )

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA10: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
