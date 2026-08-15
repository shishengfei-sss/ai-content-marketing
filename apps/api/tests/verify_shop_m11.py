#!/usr/bin/env python3
"""M11/M12 买家订单中心验收。对照 PRD 02-买家端UI.html #m11 #m12 #m12a #m12b #m12c。"""

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

MP = REPO_ROOT / "apps" / "mp" / "src"
ORDERS = MP / "pages" / "shop" / "orders.vue"
DETAIL = MP / "pages" / "shop" / "order-detail.vue"
PAGES = MP / "pages.json"


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _err_text(data) -> str:
    if not isinstance(data, dict):
        return str(data)
    d = data.get("detail", data)
    if isinstance(d, list):
        return " ".join(
            str(x.get("msg") or x.get("message") or x) if isinstance(x, dict) else str(x)
            for x in d
        )
    return str(d)


def _ensure_merchant() -> tuple[str, str]:
    from app.database import SessionLocal, uuid_eq
    from app.models import TenantMembership, TenantRole, User
    from app.models.shop import ShopMerchantAccount
    from app.services.auth_service import hash_password

    phone = "13900000097"
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
                    "tenant_name": f"M11验-{uuid.uuid4().hex[:6]}",
                    "display_name": "M11验",
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
    api_key = "mock_api_key_m11"
    code, data = req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_m11",
            "wx_app_id": "wx_mock_appid_m11",
            "wx_api_key": api_key,
            "wx_notify_url": "http://127.0.0.1:8003/api/v1/mp/shop/payments/notify",
        },
    )
    assert code == 200, data
    return api_key


def _on_sale_product(merchant: str) -> str:
    from uuid import UUID as UUIDType

    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopProduct
    from tests.http_client import _get_test_client

    client = _get_test_client()
    code, col = req(
        "POST",
        "/shop/columns",
        token=merchant,
        body={"title": f"M11col-{uuid.uuid4().hex[:6]}", "intro": "d"},
    )
    assert code in (200, 201), col
    code, les = req(
        "POST",
        f"/shop/columns/{col['id']}/lessons",
        token=merchant,
        body={
            "title": "L1",
            "duration_sec": 60,
            "media_type": "video",
            "media_url": "https://example.com/m11.mp4",
        },
    )
    assert code in (200, 201), les
    req("POST", f"/shop/columns/{col['id']}/lessons/{les['id']}/publish", token=merchant)
    req("POST", f"/shop/columns/{col['id']}/publish", token=merchant)
    cover = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {merchant}"},
        files={"file": ("c.png", b"\x89PNG", "image/png")},
    ).json()["file_url"]
    code, product = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "course",
            "name": f"M11课-{uuid.uuid4().hex[:6]}",
            "price_cents": 9900,
            "cover_url": cover,
            "ref_type": "column",
            "ref_id": col["id"],
        },
    )
    assert code in (200, 201), product
    db = SessionLocal()
    try:
        p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, UUIDType(product["id"]))).first()
        p.status = "on_sale"
        db.commit()
    finally:
        db.close()
    return product["id"]


def _buyer_order(tenant_id: str, product_id: str):
    openid = f"m11_{uuid.uuid4().hex[:10]}"
    code, bl = req(
        "POST", "/mp/shop/auth/login", body={"tenant_id": tenant_id, "code": f"mock:{openid}"}
    )
    assert code == 200, bl
    tok = bl["access_token"]
    mobile = "139" + f"{uuid.uuid4().int % 10**8:08d}"
    req("POST", "/mp/shop/auth/bind", token=tok, body={"mobile": mobile})
    code, created = req("POST", "/mp/shop/orders", token=tok, body={"product_id": product_id})
    assert code in (200, 201), created
    order = (created or {}).get("order") or created
    return tok, order


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VM11-UI-1 列表 Tab/操作矩阵",
            _page_has(ORDERS, "待付款", "已付款", "退款", "去支付", "取消", "开票", "查看进度", "#m11"),
            str(ORDERS),
        )
    )
    results.append(
        check(
            "VM11-UI-2 详情含 M12-A/B/C",
            _page_has(
                DETAIL,
                "申请退款",
                "确认取消订单",
                "退款进度",
                "质量问题",
                "该订单已开具发票",
                "buyer_request",
                "#m12a",
            )
            and "order-detail" in PAGES.read_text(encoding="utf-8"),
            str(DETAIL),
        )
    )

    merchant, tenant_id = _ensure_merchant()
    _ensure_payment(merchant)
    pid = _on_sale_product(merchant)

    buyer, pending = _buyer_order(tenant_id, pid)
    code, bad = req("POST", f"/mp/shop/orders/{pending['id']}/cancel", token=buyer)
    # first create another for pay; cancel this one
    results.append(
        check(
            "VM11-1 取消待付款",
            code == 200 and bad.get("status") == "closed",
            f"{code} {bad.get('status')}",
        )
    )

    buyer2, pending2 = _buyer_order(tenant_id, pid)
    code, paid_wrap = req("POST", f"/mp/shop/orders/{pending2['id']}/pay", token=buyer2)
    paid = (paid_wrap or {}).get("order") or paid_wrap
    results.append(
        check(
            "VM11-2 stub 去支付",
            code == 200 and paid.get("status") == "paid",
            f"{code} {paid.get('status')}",
        )
    )

    code, lst = req("GET", "/mp/shop/orders?status=paid", token=buyer2)
    results.append(
        check(
            "VM11-3 Tab 筛已付款",
            code == 200 and any(o.get("id") == paid["id"] for o in (lst.get("items") or [])),
            f"{code} {lst.get('total')}",
        )
    )

    code, detail = req("GET", f"/mp/shop/orders/{paid['id']}", token=buyer2)
    results.append(
        check(
            "VM11-4 详情含权益/轨迹",
            code == 200
            and detail.get("entitlement_status") in ("active", "pending")
            and isinstance(detail.get("timeline"), list),
            f"{code} ent={detail.get('entitlement_status')} tl={len(detail.get('timeline') or [])}",
        )
    )

    code, r = req(
        "POST",
        f"/mp/shop/orders/{paid['id']}/refund",
        token=buyer2,
        body={"reason_code": "quality"},
    )
    results.append(
        check(
            "VM11-5 M12-A 质量问题退款",
            code == 200 and "质量问题" in (r.get("reason") or ""),
            f"{code} {r.get('reason')}",
        )
    )

    code, rfs = req("GET", f"/mp/shop/orders/{paid['id']}/refunds", token=buyer2)
    results.append(
        check(
            "VM11-6 M12-C 退款进度列表",
            code == 200 and (rfs.get("total") or 0) >= 1,
            f"{code} {rfs.get('total')}",
        )
    )

    code, lst_rf = req("GET", "/mp/shop/orders?status=refund", token=buyer2)
    results.append(
        check(
            "VM11-7 Tab 退款聚合",
            code == 200
            and any(o.get("id") == paid["id"] for o in (lst_rf.get("items") or [])),
            f"{code} {lst_rf.get('total')}",
        )
    )

    # 非待付款不可取消
    code, c2 = req("POST", f"/mp/shop/orders/{paid['id']}/cancel", token=buyer2)
    results.append(
        check(
            "VM11-8 已退不可取消",
            code == 422 and "待付款" in _err_text(c2),
            f"{code} {_err_text(c2)}",
        )
    )

    passed = sum(1 for x in results if x)
    print(f"\nM11/M12: {passed}/{len(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
