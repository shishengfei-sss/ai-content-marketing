"""内容获客商城 · 开箱演示种子。

对照 docs/02-执行计划/内容获客商城-开箱即用交付标准.md §4～§5。

用法（在 apps/api，已 alembic upgrade head）::

    .venv\\Scripts\\python.exe tests/seed_shop_demo.py
    .venv\\Scripts\\python.exe tests/seed_shop_demo.py --reset-demo

幂等：按手机号 / 「演示」前缀商品 / DEMO 订单号跳过已存在记录。
``--reset-demo`` 只清 QA_DEMO_ 租户与「演示」目录/DEMO 订单，不删 13900000099 的 CRM 租户。
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal, uuid_eq  # noqa: E402
from app.models import Tenant, TenantMembership, TenantRole, User  # noqa: E402
from tests.shop_demo_urls import h5_link, web_link  # noqa: E402

from app.models.shop import (  # noqa: E402
    ShopBuyer,
    ShopClaimToken,
    ShopColumn,
    ShopDigitalAsset,
    ShopDigitalPackage,
    ShopEnrollment,
    ShopEntitlement,
    ShopLesson,
    ShopMerchantAccount,
    ShopMerchantSubscription,
    ShopOnboardingApplication,
    ShopOrder,
    ShopPaymentConfig,
    ShopProduct,
    ShopServiceOffer,
    ShopStore,
    ShopStoreSettings,
    ShopSubscriptionPlan,
)
from app.permissions import (  # noqa: E402
    PLATFORM_ADMIN_ROLE,
    PLATFORM_SHOP_ROLE_CS,
    PLATFORM_SHOP_ROLE_OPS,
)
from app.services.auth_service import hash_password  # noqa: E402
from app.services.crypto import encrypt_api_key  # noqa: E402
from app.services.membership_service import create_tenant_with_admin  # noqa: E402
from app.services.shop.a16_roles_service import _ensure_shop_roles  # noqa: E402
from app.services.shop.entitlement_service import build_plan_snapshot  # noqa: E402
from app.services.shop.platform_number_service import generate_platform_number  # noqa: E402

DEMO_PREFIX = "演示"
TENANT_PREFIX = "QA_DEMO_"
CLAIM_TOKEN = "demo_claim_token_phase1"
BUYER_OPENID = "demo_buyer_paid"
BUYER_MOBILE = "13700000001"

ACCOUNTS = {
    "platform_super": {"phone": "13800000000", "password": "admin123456", "name": "平台超管"},
    "platform_ops": {"phone": "13800000101", "password": "demo123456", "name": "演示·平台运营"},
    "platform_cs": {"phone": "13800000102", "password": "demo123456", "name": "演示·商家管家"},
    "merchant_active": {"phone": "13900000099", "password": "test123456", "name": "演示·经营中"},
    "merchant_reviewing": {"phone": "13900000101", "password": "demo123456", "name": "演示·审核中"},
    "merchant_none": {"phone": "13900000102", "password": "demo123456", "name": "演示·未入驻"},
    "merchant_suspended": {"phone": "13900000103", "password": "demo123456", "name": "演示·已暂停"},
    "merchant_closed": {"phone": "13900000104", "password": "demo123456", "name": "演示·已清退"},
}

COURSE_NAME = f"{DEMO_PREFIX}·IP获客实战课"
DIGITAL_NAME = f"{DEMO_PREFIX}·话术模板资料包"
SERVICE_NAME = f"{DEMO_PREFIX}·1v1咨询次数卡"
DRAFT_NAME = f"{DEMO_PREFIX}·草稿课（不可售）"
ORDER_PAID = "DEMOPAID0001"
ORDER_PAID_DIGITAL = "DEMOPAID0002"
ORDER_PAID_SERVICE = "DEMOPAID0003"
ORDER_PEND = "DEMOPEND0001"
ORDER_CLAIM = "DEMOCLAIM001"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _code(db, entity: str, fallback: str) -> str:
    try:
        return generate_platform_number(db, entity)
    except Exception:
        return fallback


def _ensure_user(
    db,
    *,
    phone: str,
    password: str,
    display_name: str,
    tenant_name: str | None,
    role: str = "user",
    platform_shop_role: str | None = None,
    platform_tenant_id=None,
) -> User:
    user = db.query(User).filter(User.phone == phone).first()
    if user is None:
        user = User(
            id=uuid.uuid4(),
            phone=phone,
            hashed_password=hash_password(password),
            display_name=display_name,
            role=role,
            platform_shop_role=platform_shop_role,
            is_active=True,
            tenant_id=platform_tenant_id,
        )
        db.add(user)
        db.flush()
        if tenant_name:
            existing = db.query(Tenant).filter(Tenant.name == tenant_name).first()
            if existing is None:
                create_tenant_with_admin(db, name=tenant_name, industry_code="education", user=user)
            else:
                user.tenant_id = existing.id
                role_row = (
                    db.query(TenantRole)
                    .filter(uuid_eq(TenantRole.tenant_id, existing.id), TenantRole.code == "admin")
                    .first()
                )
                if role_row and not (
                    db.query(TenantMembership)
                    .filter(
                        uuid_eq(TenantMembership.user_id, user.id),
                        uuid_eq(TenantMembership.tenant_id, existing.id),
                    )
                    .first()
                ):
                    db.add(
                        TenantMembership(
                            id=uuid.uuid4(),
                            user_id=user.id,
                            tenant_id=existing.id,
                            role_id=role_row.id,
                            is_active=True,
                        )
                    )
        db.flush()
    else:
        # SQLite 下 users.id 为 Uuid 列，ORM UPDATE 会 0 行匹配；按 phone 写。
        db.execute(
            text(
                """
                UPDATE users SET
                    is_active = :active,
                    role = CASE WHEN :force_admin = 1 THEN :admin_role ELSE role END,
                    platform_shop_role = COALESCE(:psr, platform_shop_role),
                    tenant_id = COALESCE(tenant_id, :tid)
                WHERE phone = :phone
                """
            ),
            {
                "active": True,
                "force_admin": 1 if role == PLATFORM_ADMIN_ROLE else 0,
                "admin_role": PLATFORM_ADMIN_ROLE,
                "psr": platform_shop_role,
                "tid": str(platform_tenant_id) if platform_tenant_id else None,
                "phone": phone,
            },
        )
        db.expire(user)
        user = db.query(User).filter(User.phone == phone).first()
    return user


def _bind_admin(db, user: User, tenant_id) -> None:
    _ensure_shop_roles(db, tenant_id)
    mem = (
        db.query(TenantMembership)
        .filter(uuid_eq(TenantMembership.user_id, user.id), uuid_eq(TenantMembership.tenant_id, tenant_id))
        .first()
    )
    role = (
        db.query(TenantRole)
        .filter(uuid_eq(TenantRole.tenant_id, tenant_id), TenantRole.code == "admin")
        .first()
    )
    if role is None:
        role = (
            db.query(TenantRole)
            .filter(uuid_eq(TenantRole.tenant_id, tenant_id), TenantRole.code == "shop_admin")
            .first()
        )
    if role is None:
        return
    if mem is None:
        db.add(
            TenantMembership(
                id=uuid.uuid4(),
                user_id=user.id,
                tenant_id=tenant_id,
                role_id=role.id,
                is_active=True,
            )
        )
    else:
        if str(mem.role_id) != str(role.id) or not mem.is_active:
            db.execute(
                text(
                    "UPDATE tenant_memberships SET role_id = :rid, is_active = :act WHERE id = :id"
                ),
                {"rid": str(role.id), "act": True, "id": str(mem.id)},
            )
            db.expire(mem)
    if user.tenant_id is None or str(user.tenant_id) != str(tenant_id):
        db.execute(
            text("UPDATE users SET tenant_id = :tid WHERE phone = :phone"),
            {"tid": str(tenant_id), "phone": user.phone},
        )
        db.expire(user)
        user = db.query(User).filter(User.phone == user.phone).first()
    db.flush()


def _merchant(
    db,
    *,
    tenant: Tenant,
    user: User,
    status: str,
    display_name: str,
    plan_label: str,
    plan_status: str,
    cs_id,
) -> ShopMerchantAccount:
    row = db.query(ShopMerchantAccount).filter(uuid_eq(ShopMerchantAccount.tenant_id, tenant.id)).first()
    now = _now()
    if row is None:
        row = ShopMerchantAccount(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            merchant_no=_code(db, "shop_merchant", f"DEMSH{user.phone[-4:]}"),
            entity_type="enterprise",
            legal_name=f"{display_name}主体",
            display_name=display_name,
            contact_name="演示联系人",
            contact_mobile=user.phone or "13900000000",
            status=status,
            onboarding_approved_at=now if status in ("active", "suspended", "closed") else None,
            account_manager_user_id=cs_id,
            plan_label=plan_label,
            plan_status=plan_status,
            benefits_until=(now + timedelta(days=365)).date() if status == "active" else None,
            store_count_active=0,
            store_quota=5,
            has_pending_renewal=False,
        )
        if status == "suspended":
            row.suspended_at = now
        if status == "closed":
            row.closed_at = now
            row.close_reason_code = "demo"
            row.close_reason_text = "演示清退样例"
        db.add(row)
        db.flush()
    else:
        if not row.display_name.startswith(DEMO_PREFIX) and status != "active":
            row.display_name = display_name
        row.status = status
        row.plan_label = plan_label
        row.plan_status = plan_status
        row.account_manager_user_id = cs_id or row.account_manager_user_id
        if row.store_quota is None:
            row.store_quota = 5
        db.flush()
    _bind_admin(db, user, tenant.id)
    return row


def _pending_onboarding(db, tenant: Tenant, user: User) -> ShopOnboardingApplication:
    row = (
        db.query(ShopOnboardingApplication)
        .filter(uuid_eq(ShopOnboardingApplication.tenant_id, tenant.id))
        .order_by(ShopOnboardingApplication.created_at.desc())
        .first()
    )
    if row:
        row.status = "pending"
        return row
    row = ShopOnboardingApplication(
        id=uuid.uuid4(),
        application_no=_code(db, "shop_onboarding", f"DEMOOB{user.phone[-4:]}"),
        tenant_id=tenant.id,
        entity_type="enterprise",
        initiator="merchant_self",
        status="pending",
        legal_name=f"{TENANT_PREFIX}审核中主体",
        display_name=f"{DEMO_PREFIX}·审核中商家",
        contact_name="演示联系人",
        contact_mobile=user.phone,
        qualification_files={},
        ocr_results=[],
        submitted_at=_now(),
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _ensure_stores(db, merchant: ShopMerchantAccount) -> list[ShopStore]:
    stores = (
        db.query(ShopStore)
        .filter(uuid_eq(ShopStore.tenant_id, merchant.tenant_id))
        .order_by(ShopStore.created_at.asc())
        .all()
    )
    wanted = [
        (f"{DEMO_PREFIX}·旗舰店", "demo-flagship"),
        (f"{DEMO_PREFIX}·分店", "demo-branch"),
    ]
    out: list[ShopStore] = []
    for name, slug in wanted:
        hit = next((s for s in stores if s.slug == slug), None)
        if hit is None:
            hit = ShopStore(
                id=uuid.uuid4(),
                tenant_id=merchant.tenant_id,
                merchant_id=merchant.id,
                name=name,
                slug=slug,
                status="active",
            )
            db.add(hit)
            db.flush()
            db.add(
                ShopStoreSettings(
                    id=uuid.uuid4(),
                    tenant_id=merchant.tenant_id,
                    shop_id=hit.id,
                    intro="开箱演示店铺",
                    service_phone="4000000000",
                    theme_color="#1677ff",
                )
            )
            db.flush()
        else:
            hit.status = "active"
            hit.name = name
        out.append(hit)
    merchant.store_count_active = len(out)
    db.flush()
    return out


def _product(db, *, tenant_id, shop_id, user_id, ptype, name, price, ref_type, ref_id, status, extra=None):
    row = (
        db.query(ShopProduct)
        .filter(uuid_eq(ShopProduct.tenant_id, tenant_id), ShopProduct.name == name)
        .first()
    )
    if row:
        row.status = status
        row.price_cents = price
        if ref_id:
            row.ref_type = ref_type
            row.ref_id = ref_id
        if extra:
            row.extra = extra
        if status == "on_sale" and not row.last_review_id:
            row.last_review_id = uuid.uuid4()
        db.flush()
        return row
    row = ShopProduct(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        shop_id=shop_id,
        type=ptype,
        name=name,
        price_cents=price,
        line_price_cents=price * 2 if ptype == "course" else None,
        status=status,
        ref_type=ref_type,
        ref_id=ref_id,
        last_review_id=uuid.uuid4() if status == "on_sale" else None,
        refund_policy="before_fulfill",
        extra=extra or {},
        created_by=user_id,
    )
    db.add(row)
    db.flush()
    return row


def _catalog(db, merchant: ShopMerchantAccount, shop: ShopStore, user: User) -> dict:
    tid, sid, uid = merchant.tenant_id, shop.id, user.id
    col = (
        db.query(ShopColumn)
        .filter(uuid_eq(ShopColumn.tenant_id, tid), ShopColumn.title == f"{DEMO_PREFIX}·获客专栏")
        .first()
    )
    if col is None:
        col = ShopColumn(
            id=uuid.uuid4(),
            tenant_id=tid,
            shop_id=sid,
            title=f"{DEMO_PREFIX}·获客专栏",
            intro="开箱演示专栏",
            status="published",
            created_by=uid,
        )
        db.add(col)
        db.flush()
        db.add(
            ShopLesson(
                id=uuid.uuid4(),
                tenant_id=tid,
                column_id=col.id,
                title="第 1 讲 · 开场",
                media_type="video",
                media_url="https://example.com/demo-lesson.mp4",
                duration_sec=90,
                is_trial=True,
                trial_seconds=15,
                sort_order=1,
                status="published",
            )
        )
        db.flush()
    pkg = (
        db.query(ShopDigitalPackage)
        .filter(uuid_eq(ShopDigitalPackage.tenant_id, tid), ShopDigitalPackage.title == f"{DEMO_PREFIX}·话术包")
        .first()
    )
    if pkg is None:
        pkg = ShopDigitalPackage(
            id=uuid.uuid4(),
            tenant_id=tid,
            shop_id=sid,
            title=f"{DEMO_PREFIX}·话术包",
            deliver_mode="download",
            max_downloads=5,
            status="published",
            created_by=uid,
        )
        db.add(pkg)
        db.flush()
        db.add(
            ShopDigitalAsset(
                id=uuid.uuid4(),
                tenant_id=tid,
                package_id=pkg.id,
                file_id="demo-file-1",
                file_name="话术模板.pdf",
                file_url="/storage/demo/script.pdf",
                mime="application/pdf",
                size_bytes=1024,
                previewable=True,
                sort_order=1,
            )
        )
        db.flush()
    offer = (
        db.query(ShopServiceOffer)
        .filter(uuid_eq(ShopServiceOffer.tenant_id, tid), ShopServiceOffer.title == f"{DEMO_PREFIX}·1v1咨询")
        .first()
    )
    if offer is None:
        offer = ShopServiceOffer(
            id=uuid.uuid4(),
            tenant_id=tid,
            shop_id=sid,
            title=f"{DEMO_PREFIX}·1v1咨询",
            mode="times_card",
            status="published",
            total_times=3,
            valid_days=90,
            duration_minutes=60,
            created_by=uid,
        )
        db.add(offer)
        db.flush()
    course = _product(
        db,
        tenant_id=tid,
        shop_id=sid,
        user_id=uid,
        ptype="course",
        name=COURSE_NAME,
        price=19900,
        ref_type="column",
        ref_id=col.id,
        status="on_sale",
        extra={"lesson_count": 1},
    )
    digital = _product(
        db,
        tenant_id=tid,
        shop_id=sid,
        user_id=uid,
        ptype="digital",
        name=DIGITAL_NAME,
        price=4900,
        ref_type="digital_package",
        ref_id=pkg.id,
        status="on_sale",
    )
    service = _product(
        db,
        tenant_id=tid,
        shop_id=sid,
        user_id=uid,
        ptype="service",
        name=SERVICE_NAME,
        price=59900,
        ref_type="service_offer",
        ref_id=offer.id,
        status="on_sale",
        extra={"service_times": 3},
    )
    _product(
        db,
        tenant_id=tid,
        shop_id=sid,
        user_id=uid,
        ptype="course",
        name=DRAFT_NAME,
        price=9900,
        ref_type="column",
        ref_id=col.id,
        status="draft",
    )
    return {"course": course, "digital": digital, "service": service, "shop": shop}


def _buyer(db, tenant_id) -> ShopBuyer:
    row = (
        db.query(ShopBuyer)
        .filter(uuid_eq(ShopBuyer.tenant_id, tenant_id), ShopBuyer.wx_openid == BUYER_OPENID)
        .first()
    )
    if row:
        if not row.mobile:
            row.mobile = BUYER_MOBILE
        return row
    row = ShopBuyer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        mobile=BUYER_MOBILE,
        wx_openid=BUYER_OPENID,
        nickname="演示已购买家",
    )
    db.add(row)
    db.flush()
    return row


def _order(
    db,
    *,
    no: str,
    tenant_id,
    shop_id,
    buyer: ShopBuyer,
    product: ShopProduct,
    status: str,
    source: str = "private",
    claim_token: str | None = None,
) -> ShopOrder:
    suffix = str(tenant_id).replace("-", "")[:8]
    row = (
        db.query(ShopOrder)
        .filter(
            uuid_eq(ShopOrder.tenant_id, tenant_id),
            ShopOrder.order_no.in_([no, f"{no}-{suffix}"]),
        )
        .first()
    )
    if row is None:
        row = (
            db.query(ShopOrder)
            .filter(uuid_eq(ShopOrder.tenant_id, tenant_id), ShopOrder.order_no.like(f"{no}%"))
            .first()
        )
    now = _now()
    snap = {
        "id": str(product.id),
        "name": product.name,
        "type": product.type,
        "price_cents": product.price_cents,
        "ref_type": product.ref_type,
        "ref_id": str(product.ref_id) if product.ref_id else None,
        "extra": product.extra or {},
    }
    if row is None:
        # order_no 全局唯一；其它租户已占用 DEMO 单号时给本租户加后缀
        actual_no = no
        if db.query(ShopOrder).filter(ShopOrder.order_no == actual_no).first() is not None:
            for _ in range(8):
                candidate = f"{no}-{uuid.uuid4().hex[:6]}"[:32]
                if db.query(ShopOrder).filter(ShopOrder.order_no == candidate).first() is None:
                    actual_no = candidate
                    break
        row = ShopOrder(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            shop_id=shop_id,
            buyer_id=buyer.id,
            product_id=product.id,
            product_snapshot_json=snap,
            order_no=actual_no,
            type=product.type,
            amount_cents=product.price_cents,
            status=status,
            source=source,
            buyer_mobile_snapshot=buyer.mobile,
            claim_token=claim_token,
            claim_expires_at=(now + timedelta(days=7)) if claim_token else None,
        )
        if status == "paid":
            row.paid_amount_cents = product.price_cents
            row.paid_at = now
            row.paid_channel = "stub"
        db.add(row)
        db.flush()
    if status == "paid":
        from app.services.shop.order_service import _activate_entitlement_for_order

        if row.status != "paid":
            row.status = "paid"
            row.paid_amount_cents = product.price_cents
            row.paid_at = now
            row.paid_channel = "stub"
        _activate_entitlement_for_order(db, row)
        ent = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.order_id, row.id)).first()
        if ent is not None and ent.status != "active":
            ent.status = "active"
            ent.revoked_at = None
            ent.revoke_reason = None
        db.flush()
    return row


def _ensure_claim_token(db, order: ShopOrder) -> None:
    """claim_pending 订单须有 shop_claim_tokens 行，否则 M14 GET 404。"""
    if not order.claim_token:
        return
    now = _now()
    hit = (
        db.query(ShopClaimToken)
        .filter(ShopClaimToken.token == order.claim_token)
        .first()
    )
    if hit:
        if order.status == "claim_pending" and hit.status != "pending":
            hit.status = "pending"
            hit.expires_at = order.claim_expires_at or (now + timedelta(days=7))
            hit.claimed_buyer_id = None
            hit.claimed_at = None
        return
    db.add(
        ShopClaimToken(
            id=uuid.uuid4(),
            tenant_id=order.tenant_id,
            order_id=order.id,
            buyer_mobile=order.buyer_mobile_snapshot or BUYER_MOBILE,
            token=order.claim_token,
            status="pending",
            expires_at=order.claim_expires_at or (now + timedelta(days=7)),
        )
    )
    db.flush()


def _sync_demo_claim_tokens(db) -> None:
    for order in (
        db.query(ShopOrder)
        .filter(ShopOrder.claim_token.isnot(None), ShopOrder.status == "claim_pending")
        .all()
    ):
        _ensure_claim_token(db, order)


def _plan_and_sub(db, merchant: ShopMerchantAccount, operator_id) -> None:
    plan = db.query(ShopSubscriptionPlan).filter(ShopSubscriptionPlan.code == "basic").first()
    if plan is None:
        plan = ShopSubscriptionPlan(
            id=uuid.uuid4(),
            code="basic",
            name="基础版",
            plan_type="main",
            is_public=True,
            is_active=True,
            billing_period="yearly",
            price_cents=198000,
            quotas={"store": 3},
            features={},
            usage_limits={},
            allowed_entity_types=["enterprise", "individual_business", "personal"],
            description="开箱演示套餐",
            created_by=operator_id,
        )
        db.add(plan)
        db.flush()
    sub = (
        db.query(ShopMerchantSubscription)
        .filter(uuid_eq(ShopMerchantSubscription.tenant_id, merchant.tenant_id))
        .first()
    )
    snap = build_plan_snapshot(plan)
    if sub is None:
        now = _now()
        sub = ShopMerchantSubscription(
            id=uuid.uuid4(),
            subscription_no=_code(db, "shop_subscription", "DEMOSUB0001"),
            tenant_id=merchant.tenant_id,
            plan_id=plan.id,
            status="active",
            effective_at=now,
            expires_at=now + timedelta(days=365),
            paid_at=now,
            purchase_mode="replace",
            source="manual",
            plan_snapshot=snap,
            catalog_price_cents=plan.price_cents,
            paid_amount_cents=plan.price_cents,
            operator_id=operator_id,
            remark="开箱演示开通",
        )
        db.add(sub)
        db.flush()
        merchant.current_subscription_id = sub.id
        merchant.plan_label = plan.name
        merchant.plan_status = "active"
    elif not (sub.plan_snapshot or {}).get("plan_type"):
        sub.plan_snapshot = snap
        db.flush()


def _reset_demo(db) -> None:
    """清演示目录与 QA_DEMO_ 租户的商城行；不删 13900000099 的 CRM 租户。"""
    demo_tenants = db.query(Tenant).filter(Tenant.name.like(f"{TENANT_PREFIX}%")).all()
    demo_tids = [t.id for t in demo_tenants]
    demo_products = db.query(ShopProduct).filter(ShopProduct.name.like(f"{DEMO_PREFIX}%")).all()
    pids = [p.id for p in demo_products]
    if pids:
        db.query(ShopEnrollment).filter(ShopEnrollment.course_id.in_(pids)).delete(synchronize_session=False)
        db.query(ShopEntitlement).filter(ShopEntitlement.product_id.in_(pids)).delete(synchronize_session=False)
        db.query(ShopOrder).filter(ShopOrder.product_id.in_(pids)).delete(synchronize_session=False)
        db.query(ShopProduct).filter(ShopProduct.id.in_(pids)).delete(synchronize_session=False)
    db.query(ShopOrder).filter(ShopOrder.order_no.like("DEMO%")).delete(synchronize_session=False)
    db.query(ShopBuyer).filter(ShopBuyer.wx_openid == BUYER_OPENID).delete(synchronize_session=False)
    if demo_tids:
        db.query(ShopOnboardingApplication).filter(ShopOnboardingApplication.tenant_id.in_(demo_tids)).delete(
            synchronize_session=False
        )
        db.query(ShopMerchantAccount).filter(ShopMerchantAccount.tenant_id.in_(demo_tids)).delete(
            synchronize_session=False
        )
    db.flush()
    print("reset-demo: cleared 演示 catalog / DEMO orders / QA_DEMO_ merchant rows")


def _ensure_payment_config(db, *, merchant: ShopMerchantAccount, shop: ShopStore, user_id) -> None:
    cfg = (
        db.query(ShopPaymentConfig)
        .filter(
            uuid_eq(ShopPaymentConfig.tenant_id, merchant.tenant_id),
            uuid_eq(ShopPaymentConfig.shop_id, shop.id),
        )
        .first()
    )
    if not cfg:
        cfg = ShopPaymentConfig(
            id=uuid.uuid4(),
            merchant_id=merchant.id,
            tenant_id=merchant.tenant_id,
            shop_id=shop.id,
        )
        db.add(cfg)
    cfg.wx_mch_id = "mock_mchid_demo"
    cfg.wx_app_id = "wx_mock_demo_appid"
    cfg.wx_api_key_encrypted = encrypt_api_key("mock_api_key_demo_001")
    cfg.wx_notify_url = "http://127.0.0.1:8003/api/v1/mp/shop/payments/notify"
    cfg.status = "active"
    cfg.onboarded_at = datetime.now(timezone.utc)
    cfg.onboarded_by = user_id


def seed(reset: bool = False) -> dict:
    db = SessionLocal()
    try:
        if reset:
            _reset_demo(db)
        super_cfg = ACCOUNTS["platform_super"]
        super_user = _ensure_user(
            db,
            phone=super_cfg["phone"],
            password=super_cfg["password"],
            display_name=super_cfg["name"],
            tenant_name=None,
            role=PLATFORM_ADMIN_ROLE,
        )
        if not super_user.tenant_id:
            platform_tenant = db.query(Tenant).order_by(Tenant.created_at.asc()).first()
            if platform_tenant:
                super_user.tenant_id = platform_tenant.id
        ops = _ensure_user(
            db,
            phone=ACCOUNTS["platform_ops"]["phone"],
            password=ACCOUNTS["platform_ops"]["password"],
            display_name=ACCOUNTS["platform_ops"]["name"],
            tenant_name=None,
            role=PLATFORM_ADMIN_ROLE,
            platform_shop_role=PLATFORM_SHOP_ROLE_OPS,
            platform_tenant_id=super_user.tenant_id,
        )
        cs = _ensure_user(
            db,
            phone=ACCOUNTS["platform_cs"]["phone"],
            password=ACCOUNTS["platform_cs"]["password"],
            display_name=ACCOUNTS["platform_cs"]["name"],
            tenant_name=None,
            role=PLATFORM_ADMIN_ROLE,
            platform_shop_role=PLATFORM_SHOP_ROLE_CS,
            platform_tenant_id=super_user.tenant_id,
        )

        active_cfg = ACCOUNTS["merchant_active"]
        active_user = _ensure_user(
            db,
            phone=active_cfg["phone"],
            password=active_cfg["password"],
            display_name=active_cfg["name"],
            tenant_name="演示经营中商家" if db.query(User).filter(User.phone == active_cfg["phone"]).count() == 0 else None,
        )
        if active_user.tenant_id is None:
            create_tenant_with_admin(
                db, name=f"{TENANT_PREFIX}经营中", industry_code="education", user=active_user
            )
        active_tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, active_user.tenant_id)).first()
        merchant = _merchant(
            db,
            tenant=active_tenant,
            user=active_user,
            status="active",
            display_name=f"{DEMO_PREFIX}·经营中商家",
            plan_label="基础版",
            plan_status="active",
            cs_id=cs.id,
        )
        stores = _ensure_stores(db, merchant)
        _ensure_payment_config(db, merchant=merchant, shop=stores[0], user_id=active_user.id)
        catalog = _catalog(db, merchant, stores[0], active_user)
        _plan_and_sub(db, merchant, super_user.id)
        buyer = _buyer(db, merchant.tenant_id)
        _order(
            db,
            no=ORDER_PAID,
            tenant_id=merchant.tenant_id,
            shop_id=stores[0].id,
            buyer=buyer,
            product=catalog["course"],
            status="paid",
        )
        _order(
            db,
            no=ORDER_PAID_DIGITAL,
            tenant_id=merchant.tenant_id,
            shop_id=stores[0].id,
            buyer=buyer,
            product=catalog["digital"],
            status="paid",
        )
        _order(
            db,
            no=ORDER_PAID_SERVICE,
            tenant_id=merchant.tenant_id,
            shop_id=stores[0].id,
            buyer=buyer,
            product=catalog["service"],
            status="paid",
        )
        _order(
            db,
            no=ORDER_PEND,
            tenant_id=merchant.tenant_id,
            shop_id=stores[0].id,
            buyer=buyer,
            product=catalog["digital"],
            status="pending_payment",
        )
        claim_order = _order(
            db,
            no=ORDER_CLAIM,
            tenant_id=merchant.tenant_id,
            shop_id=stores[0].id,
            buyer=buyer,
            product=catalog["course"],
            status="claim_pending",
            source="public_douyin",
            claim_token=CLAIM_TOKEN,
        )
        _ensure_claim_token(db, claim_order)
        _sync_demo_claim_tokens(db)

        for key, status, plan_status, tname in (
            ("merchant_suspended", "suspended", "active", f"{TENANT_PREFIX}已暂停"),
            ("merchant_closed", "closed", "expired", f"{TENANT_PREFIX}已清退"),
        ):
            cfg = ACCOUNTS[key]
            u = _ensure_user(
                db,
                phone=cfg["phone"],
                password=cfg["password"],
                display_name=cfg["name"],
                tenant_name=tname,
            )
            ten = db.query(Tenant).filter(uuid_eq(Tenant.id, u.tenant_id)).first()
            _merchant(
                db,
                tenant=ten,
                user=u,
                status=status,
                display_name=cfg["name"] + "商家",
                plan_label="基础版",
                plan_status=plan_status,
                cs_id=cs.id,
            )

        rev = ACCOUNTS["merchant_reviewing"]
        ru = _ensure_user(
            db,
            phone=rev["phone"],
            password=rev["password"],
            display_name=rev["name"],
            tenant_name=f"{TENANT_PREFIX}审核中",
        )
        rten = db.query(Tenant).filter(uuid_eq(Tenant.id, ru.tenant_id)).first()
        _pending_onboarding(db, rten, ru)
        _bind_admin(db, ru, rten.id)

        none = ACCOUNTS["merchant_none"]
        nu = _ensure_user(
            db,
            phone=none["phone"],
            password=none["password"],
            display_name=none["name"],
            tenant_name=f"{TENANT_PREFIX}未入驻",
        )
        _bind_admin(db, nu, nu.tenant_id)

        db.commit()
        return {
            "tenant_id": str(merchant.tenant_id),
            "shop_id": str(stores[0].id),
            "claim_token": CLAIM_TOKEN,
            "buyer_openid": BUYER_OPENID,
            "accounts": ACCOUNTS,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def print_table(info: dict) -> None:
    print("")
    print("=== 演示账号（与启动说明一致）===")
    rows = [
        ("平台超管", ACCOUNTS["platform_super"], "/admin/login · workspace=platform"),
        ("平台运营", ACCOUNTS["platform_ops"], "/admin/login"),
        ("商家管家", ACCOUNTS["platform_cs"], "/admin/login · 可代建入驻"),
        ("商家-经营中", ACCOUNTS["merchant_active"], "/login → /shop"),
        ("商家-审核中", ACCOUNTS["merchant_reviewing"], "/login · 横幅审核中"),
        ("商家-未入驻", ACCOUNTS["merchant_none"], "/login → 开通商城"),
        ("商家-已暂停", ACCOUNTS["merchant_suspended"], "/login"),
        ("商家-已清退", ACCOUNTS["merchant_closed"], "/login · 只读"),
    ]
    for label, acc, hint in rows:
        print(f"  {label:12} {acc['phone']}  {acc['password']:12}  {hint}")
    print("")
    print(f"经营中 tenant_id = {info['tenant_id']}")
    print(f"平台登录      = {web_link('/admin/login')}")
    print(f"商家登录      = {web_link('/login')}")
    print(
        f"店首页（H5）  = {h5_link(f'#/pages/shop/home?shop_id={info['shop_id']}&tenant_id={info['tenant_id']}&openid={info['buyer_openid']}')}"
    )
    print(
        f"买家已购（H5）= {h5_link(f'#/pages/shop/entitlements?tenant_id={info['tenant_id']}&openid={info['buyer_openid']}')}"
    )
    print(
        f"领权（H5）    = {h5_link(f'#/pages/shop/claim?token={info['claim_token']}&tenant_id={info['tenant_id']}')}"
    )
    print("买家无独立密码：H5 Mock 登录（openid）。短信验证码固定 1111。")


def main() -> int:
    parser = argparse.ArgumentParser(description="商城开箱演示种子")
    parser.add_argument("--reset-demo", action="store_true", help="清演示目录后重建")
    args = parser.parse_args()
    info = seed(reset=args.reset_demo)
    print("seed_shop_demo: ok")
    print_table(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
