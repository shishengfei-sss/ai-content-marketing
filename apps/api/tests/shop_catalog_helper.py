"""创建可提审/上架的演示商品（封面 + CMS 引用）。"""
from __future__ import annotations

import uuid

from tests.http_client import _get_test_client, req


def ensure_demo_merchant_admin(phone: str = "13900000099") -> str | None:
    """把演示商家绑到企业管理员，并补齐 admin 角色的 shop.* 权限。返回 tenant_id。"""
    from sqlalchemy import text

    from app.database import SessionLocal, uuid_eq
    from app.models import TenantMembership, TenantRole, TenantRolePermission, User
    from app.models.shop import ShopMerchantAccount, ShopStore
    from app.permissions import ALL_PERMISSIONS, SYSTEM_ROLE_ADMIN
    from app.services.shop.a16_roles_service import _ensure_shop_roles

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            return None
        mems = (
            db.query(TenantMembership)
            .filter(uuid_eq(TenantMembership.user_id, user.id), TenantMembership.is_active.is_(True))
            .all()
        )
        tids = [m.tenant_id for m in mems]
        if user.tenant_id:
            tids.insert(0, user.tenant_id)
        merchant = None
        q = db.query(ShopMerchantAccount)
        if user.tenant_id:
            merchant = q.filter(uuid_eq(ShopMerchantAccount.tenant_id, user.tenant_id)).first()
        if merchant is None and tids:
            admin_tids = []
            for m in mems:
                role = getattr(m, "role", None)
                if role is None:
                    role = (
                        db.query(TenantRole)
                        .filter(uuid_eq(TenantRole.id, m.role_id))
                        .first()
                    )
                if role is not None and role.code == SYSTEM_ROLE_ADMIN:
                    admin_tids.append(m.tenant_id)
            merchant = (
                q.filter(ShopMerchantAccount.tenant_id.in_(admin_tids or tids))
                .order_by(ShopMerchantAccount.created_at.asc())
                .first()
            )
        if merchant is None:
            merchant = (
                db.query(ShopMerchantAccount)
                .filter(ShopMerchantAccount.status == "active")
                .order_by(ShopMerchantAccount.created_at.asc())
                .first()
            )
        tid = merchant.tenant_id if merchant else user.tenant_id
        if not tid:
            return None
        _ensure_shop_roles(db, tid)
        admin_role = (
            db.query(TenantRole)
            .filter(uuid_eq(TenantRole.tenant_id, tid), TenantRole.code == SYSTEM_ROLE_ADMIN)
            .first()
        )
        if admin_role is None:
            admin_role = TenantRole(
                id=uuid.uuid4(),
                tenant_id=tid,
                code=SYSTEM_ROLE_ADMIN,
                name="企业管理员",
                is_system=True,
            )
            db.add(admin_role)
            db.flush()
        if admin_role:
            existing = {
                p.permission_code
                for p in db.query(TenantRolePermission)
                .filter(uuid_eq(TenantRolePermission.role_id, admin_role.id))
                .all()
            }
            for code in ALL_PERMISSIONS:
                if code not in existing:
                    db.add(TenantRolePermission(role_id=admin_role.id, permission_code=code))
            mem = (
                db.query(TenantMembership)
                .filter(uuid_eq(TenantMembership.user_id, user.id), uuid_eq(TenantMembership.tenant_id, tid))
                .first()
            )
            # SQLite 存 UUID 无连字符；带连字符的 WHERE id=:id 会 0 行
            rid_hex = admin_role.id.hex
            if mem:
                db.execute(
                    text(
                        "UPDATE tenant_memberships SET role_id = :rid, is_active = 1 "
                        "WHERE lower(replace(id, '-', '')) = :mid"
                    ),
                    {"rid": rid_hex, "mid": mem.id.hex},
                )
                db.expunge(mem)
            else:
                db.add(
                    TenantMembership(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        tenant_id=tid,
                        role_id=admin_role.id,
                        is_active=True,
                    )
                )
        db.execute(
            text("UPDATE users SET tenant_id = :tid WHERE phone = :phone"),
            {"tid": tid.hex if hasattr(tid, "hex") else str(tid).replace("-", ""), "phone": phone},
        )
        db.expunge(user)
        if merchant is not None and merchant.status == "suspended":
            merchant.status = "active"
        if tid:
            db.query(ShopStore).filter(
                uuid_eq(ShopStore.tenant_id, tid), ShopStore.status == "paused"
            ).update({"status": "active"}, synchronize_session=False)
        db.commit()
        return str(tid)
    finally:
        db.close()


def resolve_tenant_id(token: str) -> str:
    code, me = req("GET", "/auth/me", token=token)
    assert code == 200, me
    tid = (me.get("active_tenant") or {}).get("id")
    assert tid, me
    return str(tid)


def buyer_token(tenant_id: str, openid: str | None = None) -> str:
    oid = openid or f"e2e_{uuid.uuid4().hex[:8]}"
    code, data = req(
        "POST", "/mp/shop/auth/login", body={"tenant_id": tenant_id, "code": f"mock:{oid}"}
    )
    assert code == 200, data
    return data["access_token"]


def upload_cover(merchant: str) -> str:
    client = _get_test_client()
    r = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {merchant}"},
        files={"file": ("c.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["file_url"]


def ensure_cms_ref(merchant: str, product_type: str) -> tuple[str, str]:
    tag = uuid.uuid4().hex[:6]
    if product_type == "course":
        code, col = req(
            "POST",
            "/shop/columns",
            token=merchant,
            body={"title": f"验收专栏-{tag}", "intro": "d"},
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
                "media_url": "https://example.com/lesson.mp4",
            },
        )
        assert code in (200, 201), les
        req("POST", f"/shop/columns/{col['id']}/lessons/{les['id']}/publish", token=merchant)
        req("POST", f"/shop/columns/{col['id']}/publish", token=merchant)
        return "column", col["id"]
    if product_type == "digital":
        code, pkg = req(
            "POST",
            "/shop/digital-packages",
            token=merchant,
            body={"title": f"验收资料包-{tag}", "deliver_mode": "download", "max_downloads": 3},
        )
        assert code in (200, 201), pkg
        cover = upload_cover(merchant)
        client = _get_test_client()
        pdf = client.post(
            "/api/v1/shop/content/files",
            headers={"Authorization": f"Bearer {merchant}"},
            files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")},
        ).json()
        req(
            "POST",
            f"/shop/digital-packages/{pkg['id']}/assets",
            token=merchant,
            body={
                "file_id": pdf["file_id"],
                "file_name": pdf.get("file_name") or "a.pdf",
                "file_url": pdf["file_url"],
                "mime": pdf.get("mime") or "application/pdf",
                "size_bytes": pdf.get("size_bytes") or 8,
            },
        )
        req("POST", f"/shop/digital-packages/{pkg['id']}/publish", token=merchant)
        return "digital_package", pkg["id"]
    code, offer = req(
        "POST",
        "/shop/service-offers",
        token=merchant,
        body={
            "title": f"验收服务-{tag}",
            "mode": "times_card",
            "total_times": 2,
            "valid_days": 90,
            "duration_minutes": 60,
        },
    )
    assert code in (200, 201), offer
    req("POST", f"/shop/service-offers/{offer['id']}/publish", token=merchant)
    return "service_offer", offer["id"]


def ensure_payment_config(merchant: str, api_key: str = "mock_api_key_e2e") -> str:
    code, existing = req("GET", "/shop/payment-config", token=merchant)
    if code == 200 and isinstance(existing, dict) and existing.get("wx_mch_id"):
        return api_key
    code, data = req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_e2e",
            "wx_app_id": "wx_mock_appid_e2e",
            "wx_api_key": api_key,
            "wx_notify_url": "http://127.0.0.1:8003/api/v1/mp/shop/payments/notify",
        },
    )
    assert code == 200, data
    return api_key


def ensure_on_sale_product(
    merchant: str,
    product_type: str = "course",
    *,
    price_cents: int = 9900,
    extra: dict | None = None,
    admin_token: str | None = None,
) -> str:
    if not admin_token:
        code, data = req(
            "POST", "/auth/login", body={"phone": "13800000000", "password": "admin123456"}
        )
        assert code == 200, data
        admin_token = data["access_token"]
    ensure_payment_config(merchant)
    cover = upload_cover(merchant)
    ref_type, ref_id = ensure_cms_ref(merchant, product_type)
    body = {
        "type": product_type,
        "name": f"验收-{product_type}-{uuid.uuid4().hex[:6]}",
        "price_cents": price_cents,
        "refund_policy": "always_allow",
        "cover_url": cover,
        "ref_type": ref_type,
        "ref_id": ref_id,
    }
    if extra:
        body.update(extra)
    code, data = req("POST", "/shop/products", token=merchant, body=body)
    assert code == 200, data
    pid = data["id"]
    code, data = req("POST", f"/shop/products/{pid}/submit-review", token=merchant, body={})
    assert code == 200, data
    rid = data["review_id"]
    code, data = req("POST", f"/admin/shop/product-reviews/{rid}/approve", token=admin_token)
    assert code == 200, data
    code, data = req("POST", f"/shop/products/{pid}/publish", token=merchant)
    assert code == 200 and data.get("status") == "on_sale", data
    return pid
