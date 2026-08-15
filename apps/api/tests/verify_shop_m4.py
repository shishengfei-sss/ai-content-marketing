#!/usr/bin/env python3
"""M4 商品与审核验收。对照执行计划 §8.2 VS-M4-01～08。"""

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


def _ensure_merchant_token() -> str:
    """保证测试商家账号挂在 active merchant 租户上。"""
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
            # 走注册
            db.close()
            code, data = req(
                "POST",
                "/auth/register",
                body={
                    "phone": phone,
                    "password": password,
                    "tenant_name": f"M4商户-{uuid.uuid4().hex[:6]}",
                    "display_name": "M4测试",
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

        # 绑定 membership + 默认角色含 shop.product.*
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
            mem = TenantMembership(
                id=uuid.uuid4(),
                user_id=user.id,
                tenant_id=merchant.tenant_id,
                role_id=role.id,
                is_active=True,
            )
            db.add(mem)
        elif mem is not None and role is not None:
            mem.role_id = role.id
            mem.is_active = True
        user.tenant_id = merchant.tenant_id
        user.hashed_password = hash_password(password)
        db.commit()
    finally:
        db.close()
    return login(phone, password)


def _upload(token: str, name: str, content: bytes, mime: str) -> dict:
    from tests.http_client import USE_LIVE, _get_test_client

    if USE_LIVE:
        raise RuntimeError("M4 upload requires TestClient")
    client = _get_test_client()
    r = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (name, content, mime)},
    )
    data = r.json()
    assert r.status_code == 200, data
    return data


def _ensure_cms_refs(merchant: str) -> dict:
    """提审必填关联内容：专栏 / 资料包 / 服务。"""
    cover = _upload(merchant, "cover.png", b"\x89PNG\r\n\x1a\nfake", "image/png")
    code, col = req(
        "POST", "/shop/columns", token=merchant, body={"title": f"M4专栏-{uuid.uuid4().hex[:6]}"}
    )
    assert code == 201, col
    media = _upload(merchant, "l1.mp4", b"fake-vid", "video/mp4")
    code, les = req(
        "POST",
        f"/shop/columns/{col['id']}/lessons",
        token=merchant,
        body={
            "title": "M4课时",
            "media_type": "video",
            "media_id": media["file_id"],
            "media_url": media["file_url"],
            "duration_sec": 60,
        },
    )
    assert code == 201, les
    code, _ = req("POST", f"/shop/columns/{col['id']}/lessons/{les['id']}/publish", token=merchant)
    assert code == 200
    code, _ = req("POST", f"/shop/columns/{col['id']}/publish", token=merchant)
    assert code == 200

    code, pkg = req(
        "POST",
        "/shop/digital-packages",
        token=merchant,
        body={"title": f"M4资料-{uuid.uuid4().hex[:6]}", "deliver_mode": "download", "max_downloads": 3},
    )
    assert code == 201, pkg
    pdf = _upload(merchant, "m4.pdf", b"%PDF-1.4 m4", "application/pdf")
    code, _ = req(
        "POST",
        f"/shop/digital-packages/{pkg['id']}/assets",
        token=merchant,
        body={
            "file_id": pdf["file_id"],
            "file_name": pdf["file_name"],
            "file_url": pdf["file_url"],
            "mime": pdf["mime"],
            "size_bytes": pdf["size_bytes"],
        },
    )
    assert code == 201
    code, _ = req("POST", f"/shop/digital-packages/{pkg['id']}/publish", token=merchant)
    assert code == 200

    code, offer = req(
        "POST",
        "/shop/service-offers",
        token=merchant,
        body={
            "title": f"M4服务-{uuid.uuid4().hex[:6]}",
            "mode": "times_card",
            "total_times": 3,
            "valid_days": 90,
            "duration_minutes": 60,
        },
    )
    assert code == 201, offer
    code, _ = req("POST", f"/shop/service-offers/{offer['id']}/publish", token=merchant)
    assert code == 200

    return {
        "cover_url": cover["file_url"],
        "column_id": col["id"],
        "package_id": pkg["id"],
        "offer_id": offer["id"],
    }


def main() -> int:
    results: list[bool] = []
    from types import SimpleNamespace

    from fastapi import HTTPException
    from app.services.shop.product_service import PRODUCT_TRANSITION_ACTIONS, transition_product

    pub_from = PRODUCT_TRANSITION_ACTIONS["publish"][0]
    results.append(
        check("VS-M4-SM 禁止 draft→on_sale", "draft" not in pub_from, str(sorted(pub_from)))
    )
    results.append(
        check("VS-M4-SM 禁止 rejected→on_sale", "rejected" not in pub_from, str(sorted(pub_from)))
    )
    try:
        transition_product(SimpleNamespace(status="draft"), "publish")
        sm_ok, sm_detail = False, "no exception"
    except HTTPException as e:
        sm_ok = e.status_code == 422 and "上架" in str(e.detail)
        sm_detail = str(e.detail)
    results.append(check("VS-M4-SM draft 上架 422", sm_ok, sm_detail))

    admin = login("13800000000", "admin123456")
    merchant = _ensure_merchant_token()
    refs = _ensure_cms_refs(merchant)
    cover = refs["cover_url"]

    # VS-M4-01 三类草稿
    created_ids = []
    for ptype, name, rtype, rid in (
        ("course", "M4课程草稿", "column", refs["column_id"]),
        ("digital", "M4资料草稿", "digital_package", refs["package_id"]),
        ("service", "M4服务草稿", "service_offer", refs["offer_id"]),
    ):
        code, data = req(
            "POST",
            "/shop/products",
            token=merchant,
            body={
                "type": ptype,
                "name": name,
                "price_cents": 9900,
                "cover_url": cover,
                "ref_type": rtype,
                "ref_id": rid,
            },
        )
        ok = code == 200 and data.get("status") == "draft" and data.get("type") == ptype
        if ok:
            created_ids.append(data["id"])
        results.append(check(f"VS-M4-01 创建{ptype}草稿", ok, f"{code} {data}"))

    pid = created_ids[0] if created_ids else None

    # VS-M4-05 机审敏感词
    code_bad, bad = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "course",
            "name": "含违禁内容课",
            "price_cents": 100,
            "cover_url": cover,
            "ref_type": "column",
            "ref_id": refs["column_id"],
        },
    )
    if code_bad == 200:
        code_sr, sr = req("POST", f"/shop/products/{bad['id']}/submit-review", token=merchant, body={})
        results.append(
            check("VS-M4-05 机审命中不可通过", code_sr == 422 and "机审" in str(sr), f"{code_sr} {sr}")
        )
    else:
        results.append(check("VS-M4-05 机审命中不可通过", False, str(bad)))

    # VS-M4-02 提审
    if pid:
        code, data = req("POST", f"/shop/products/{pid}/submit-review", token=merchant, body={})
        results.append(
            check(
                "VS-M4-02 提审→pending_review",
                code == 200 and data.get("status") == "pending_review",
                f"{code} {data}",
            )
        )
        review_id = data.get("review_id")
    else:
        results.append(check("VS-M4-02 提审→pending_review", False, "no pid"))
        review_id = None

    # VS-M4-07 禁止直改 status
    if pid:
        code, data = req(
            "PATCH",
            f"/shop/products/{pid}",
            token=merchant,
            body={"name": "改名测试"},
        )
        # pending 不可编辑
        results.append(
            check("VS-M4-07 审核中不可改核心字段", code == 422, f"{code} {data}")
        )
    else:
        results.append(check("VS-M4-07 审核中不可改核心字段", False, "no pid"))

    # VS-M4-06 无 product.review → 403（管家）
    from app.database import SessionLocal
    from app.models import User
    from app.permissions import PLATFORM_ADMIN_ROLE, PLATFORM_SHOP_ROLE_CS
    from app.services.auth_service import hash_password

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.phone == "13800000088").first()
        if not u:
            u = User(
                id=uuid.uuid4(),
                phone="13800000088",
                hashed_password=hash_password("cs12345678"),
                display_name="CS",
                role=PLATFORM_ADMIN_ROLE,
                platform_shop_role=PLATFORM_SHOP_ROLE_CS,
            )
            db.add(u)
        else:
            u.platform_shop_role = PLATFORM_SHOP_ROLE_CS
        db.commit()
    finally:
        db.close()
    cs = login("13800000088", "cs12345678")
    code, data = req("GET", "/admin/shop/product-reviews", token=cs)
    results.append(check("VS-M4-06 无 review → 403", code == 403, f"{code}"))

    # VS-M4-03 人审通过→可 on_sale
    if review_id:
        code_a, rev = req("POST", f"/admin/shop/product-reviews/{review_id}/approve", token=admin)
        code_p, pub = req("POST", f"/shop/products/{pid}/publish", token=merchant)
        results.append(
            check(
                "VS-M4-03 通过后可上架",
                code_a == 200
                and rev.get("manual_result") == "approved"
                and code_p == 200
                and pub.get("status") == "on_sale",
                f"a={code_a} p={code_p} {pub}",
            )
        )
    else:
        results.append(check("VS-M4-03 通过后可上架", False, "no review"))

    # VS-M4-04 驳回路径：再建一个提审后驳回
    code, draft = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "digital",
            "name": "待驳回资料",
            "price_cents": 100,
            "cover_url": cover,
            "ref_type": "digital_package",
            "ref_id": refs["package_id"],
        },
    )
    if code == 200:
        code_s, sub = req("POST", f"/shop/products/{draft['id']}/submit-review", token=merchant, body={})
        rid = sub.get("review_id")
        code_r, rej = req(
            "POST",
            f"/admin/shop/product-reviews/{rid}/reject",
            token=admin,
            body={"reject_reason": "资料不完整请补充"},
        )
        code_pub, pub2 = req("POST", f"/shop/products/{draft['id']}/publish", token=merchant)
        results.append(
            check(
                "VS-M4-04 驳回后不可上架",
                code_r == 200
                and rej.get("manual_result") == "rejected"
                and code_pub == 422,
                f"r={code_r} pub={code_pub}",
            )
        )
        # 改稿重提
        code_e, _ = req(
            "PATCH",
            f"/shop/products/{draft['id']}",
            token=merchant,
            body={"name": "待驳回资料-已改"},
        )
        code_s2, sub2 = req(
            "POST", f"/shop/products/{draft['id']}/submit-review", token=merchant, body={}
        )
        results.append(
            check(
                "VS-M4-04b 驳回后可改稿重提",
                code_e == 200 and code_s2 == 200 and sub2.get("status") == "pending_review",
                f"e={code_e} s2={code_s2}",
            )
        )
    else:
        results.append(check("VS-M4-04 驳回后不可上架", False, str(draft)))
        results.append(check("VS-M4-04b 驳回后可改稿重提", False, "skip"))

    # VS-M4-08 审计字段
    if review_id:
        code, detail = req("GET", f"/admin/shop/product-reviews/{review_id}", token=admin)
        results.append(
            check(
                "VS-M4-08 审核留痕",
                code == 200
                and detail.get("reviewer_id")
                and detail.get("reviewed_at")
                and detail.get("manual_result") == "approved",
                str(detail)[:200],
            )
        )
    else:
        results.append(check("VS-M4-08 审核留痕", False, "no review"))

    web = API_ROOT.parent / "web" / "src" / "views"
    pe = (web / "shop" / "ProductEdit.vue").read_text(encoding="utf-8") if (web / "shop" / "ProductEdit.vue").is_file() else ""
    results.append(
        check(
            "VS-M4-UI A02/A03",
            (web / "shop" / "ProductsList.vue").is_file()
            and (web / "admin" / "shop" / "ProductReviews.vue").is_file()
            and "关联专栏" in pe
            and "关联资料包" in pe
            and "关联服务" in pe,
            "",
        )
    )

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'PASS' if passed == total else 'FAIL'} {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
