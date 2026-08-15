#!/usr/bin/env python3
"""A03 商品编辑 · 关联 CMS。对照 PRD 01-管理端UI.html #a03 / #a03-select-spec。"""

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


def _ensure_merchant() -> str:
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
                    "tenant_name": f"A03验-{uuid.uuid4().hex[:6]}",
                    "display_name": "A03验",
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
    finally:
        db.close()
    return login(phone, password)


def _upload(token: str, name: str, content: bytes, mime: str) -> dict:
    from tests.http_client import USE_LIVE, _get_test_client

    assert not USE_LIVE
    client = _get_test_client()
    r = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (name, content, mime)},
    )
    data = r.json()
    assert r.status_code == 200, data
    return data


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "UI A03 三态关联",
            _page_has(
                WEB / "ProductEdit.vue",
                "关联专栏",
                "关联资料包",
                "关联服务",
                "专栏摘要",
                "资料摘要",
                "服务摘要",
                "退款策略",
                "存草稿",
                "提交审核",
            ),
        )
    )
    results.append(
        check(
            "UI A02 行操作",
            _page_has(
                WEB / "ProductsList.vue",
                "新建商品",
                "提交审核",
                "撤回",
                'label="关联"',
                "ShopProductNew",
            ),
        )
    )

    merchant = _ensure_merchant()
    cover = _upload(merchant, "a03-cover.png", b"\x89PNG fake", "image/png")["file_url"]

    # 无关联不可提审
    code, bare = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={"type": "course", "name": f"裸课-{uuid.uuid4().hex[:6]}", "price_cents": 100, "cover_url": cover},
    )
    results.append(check("VA03-1 可建无关联草稿", code == 200, f"{code} {bare}"))
    code, no_ref = req("POST", f"/shop/products/{bare['id']}/submit-review", token=merchant, body={})
    results.append(check("VA03-2 无专栏不可提审", code == 422 and "专栏" in str(no_ref), f"{code} {no_ref}"))

    # 发布专栏并挂载
    code, col = req(
        "POST", "/shop/columns", token=merchant, body={"title": f"A03专栏-{uuid.uuid4().hex[:6]}"}
    )
    results.append(check("VA03-3 建专栏", code == 201, f"{code} {col}"))
    media = _upload(merchant, "a03.mp4", b"vid", "video/mp4")
    code, les = req(
        "POST",
        f"/shop/columns/{col['id']}/lessons",
        token=merchant,
        body={
            "title": "A03课",
            "media_type": "video",
            "media_id": media["file_id"],
            "media_url": media["file_url"],
            "duration_sec": 120,
        },
    )
    req("POST", f"/shop/columns/{col['id']}/lessons/{les['id']}/publish", token=merchant)
    req("POST", f"/shop/columns/{col['id']}/publish", token=merchant)

    code, patched = req(
        "PATCH",
        f"/shop/products/{bare['id']}",
        token=merchant,
        body={"ref_type": "column", "ref_id": col["id"], "extra": {"intro": "A03简介"}},
    )
    results.append(
        check(
            "VA03-4 patch 关联专栏",
            code == 200 and patched.get("ref_id") == col["id"] and (patched.get("extra") or {}).get("intro") == "A03简介",
            f"{code} {patched}",
        )
    )

    code, sub = req("POST", f"/shop/products/{bare['id']}/submit-review", token=merchant, body={})
    results.append(
        check("VA03-5 有关联可提审", code == 200 and sub.get("status") == "pending_review", f"{code} {sub}")
    )

    code, wd = req("POST", f"/shop/products/{bare['id']}/withdraw", token=merchant)
    results.append(check("VA03-6 撤回→草稿", code == 200 and wd.get("status") == "draft", f"{code} {wd}"))

    # 资料包关联
    code, pkg = req(
        "POST",
        "/shop/digital-packages",
        token=merchant,
        body={"title": f"A03包-{uuid.uuid4().hex[:6]}", "deliver_mode": "download", "max_downloads": 2},
    )
    pdf = _upload(merchant, "a03.pdf", b"%PDF a03", "application/pdf")
    req(
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
    req("POST", f"/shop/digital-packages/{pkg['id']}/publish", token=merchant)
    code, dig = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "digital",
            "name": f"A03资料-{uuid.uuid4().hex[:6]}",
            "price_cents": 4900,
            "cover_url": cover,
            "ref_type": "digital_package",
            "ref_id": pkg["id"],
        },
    )
    results.append(
        check(
            "VA03-7 资料商品挂包",
            code == 200 and dig.get("ref_type") == "digital_package",
            f"{code} {dig}",
        )
    )
    code, dig_sub = req("POST", f"/shop/products/{dig['id']}/submit-review", token=merchant, body={})
    results.append(check("VA03-8 资料可提审", code == 200, f"{code} {dig_sub}"))

    # 错绑类型
    code, bad = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "course",
            "name": "错绑",
            "price_cents": 1,
            "cover_url": cover,
            "ref_type": "digital_package",
            "ref_id": pkg["id"],
        },
    )
    results.append(check("VA03-9 类型不匹配 422", code == 422, f"{code} {bad}"))

    # 无封面不可提审
    code, noc = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "course",
            "name": f"无封面-{uuid.uuid4().hex[:6]}",
            "price_cents": 100,
            "ref_type": "column",
            "ref_id": col["id"],
        },
    )
    code2, sr2 = req("POST", f"/shop/products/{noc['id']}/submit-review", token=merchant, body={})
    results.append(check("VA03-10 无封面不可提审", code2 == 422 and "封面" in str(sr2), f"{code2} {sr2}"))

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA03: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
