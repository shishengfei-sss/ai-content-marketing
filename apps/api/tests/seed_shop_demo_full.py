"""内容获客商城 · 验收演示量级种子。

在开箱最小集（seed_shop_demo）之上，灌入 4 家经营中商家，每家约 30～50 条：
商品、订单、买家、专栏、资料包、服务、预约、核销、发票、公域映射、服务记录等。

用法（在 apps/api，已 alembic upgrade head）::

    .venv\\Scripts\\python.exe tests/seed_shop_demo_full.py
    .venv\\Scripts\\python.exe tests/seed_shop_demo_full.py --reset-volume

幂等：按商品名 / DEMOVOL 订单号 / 买家 openid 跳过已存在记录。
``--reset-volume`` 只清「演示量」目录、DEMOVOL 订单、QA_DEMO_验收 租户商城行，
不影响开箱最小集（演示课 / DEMOPAID 等）。
"""
from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal, uuid_eq  # noqa: E402
from app.models import Tenant, User  # noqa: E402
from app.models.shop import (  # noqa: E402
    ShopBooking,
    ShopBuyer,
    ShopChannelAuditLog,
    ShopChannelMapping,
    ShopClaimToken,
    ShopColumn,
    ShopDigitalAsset,
    ShopDigitalDownload,
    ShopDigitalPackage,
    ShopEnrollment,
    ShopEntitlement,
    ShopInvoiceRequest,
    ShopLesson,
    ShopLessonProgress,
    ShopMerchantAccount,
    ShopMerchantServiceLog,
    ShopMerchantSubscription,
    ShopMerchantTag,
    ShopMerchantTagLink,
    ShopModerationCase,
    ShopPaymentOnboarding,
    ShopPlatformCategory,
    ShopOnboardingApplication,
    ShopOrder,
    ShopPayment,
    ShopPaymentLog,
    ShopProduct,
    ShopProductReview,
    ShopRefund,
    ShopServiceOffer,
    ShopServiceSlot,
    ShopSettlementBatch,
    ShopSettlementItem,
    ShopSmsLog,
    ShopStore,
    ShopVerification,
    ShopAuditLog,
    ShopChannelSetting,
)
from tests.shop_demo_urls import h5_link, web_link  # noqa: E402
from tests.seed_shop_demo import (  # noqa: E402
    ACCOUNTS,
    _bind_admin,
    _code,
    _ensure_payment_config,
    _ensure_stores,
    _ensure_user,
    _merchant,
    _now,
    _plan_and_sub,
    seed as seed_min,
)

VOLUME_PREFIX = "演示量"
ORDER_PREFIX = "DEMOVOL"
BUYER_OPENID_PREFIX = "demo_vol_"
TENANT_PREFIX = "QA_DEMO_验收"
VOLUME_PASSWORD = "demo123456"
LIST_TARGET = 36  # 各列表约 30～50 的中间量

COURSE_STEMS = [
    "私域获客从0到1",
    "短视频脚本拆解",
    "直播带货话术实战",
    "朋友圈运营日历",
    "成交异议处理",
    "线索培育七步法",
    "IP人设打造",
    "社群裂变玩法",
    "小红书笔记爆款",
    "微信视频号运营",
    "销售教练陪跑课",
    "内容选题库训练",
    "客户画像工作坊",
    "报价与逼单技巧",
    "复购与转介绍",
    "门店私域SOP",
    "新品发布会复盘",
    "投放获客入门",
    "企微托管实战",
    "高客单成交课",
]
DIGITAL_STEMS = [
    "话术模板资料包",
    "朋友圈文案日历",
    "短视频脚本库",
    "报价单模板包",
    "客户跟进表",
    "裂变海报素材",
    "直播话术卡",
    "异议应对手册",
    "SOP流程图包",
    "案例拆解合集",
    "岗位职责模板",
    "培训课件PPT",
    "获客清单Excel",
    "转化漏斗画布",
]
SERVICE_STEMS = [
    "1v1获客诊断",
    "陪跑咨询次数卡",
    "直播场控陪跑",
    "脚本代写服务",
    "人设咨询工作坊",
    "私域搭建陪跑",
    "投放账户诊断",
    "成交陪练",
    "社群代运营体验",
    "内容日历共创",
    "销冠陪访",
    "复盘工作坊",
    "门店巡店辅导",
    "新品发布陪跑",
]

VOLUME_MERCHANTS = [
    {
        "idx": 1,
        "phone": "13900000099",
        "password": "test123456",
        "display_name": "演示·经营中商家",
        "account_name": "演示·经营中",
        "tag": "旗舰",
        "tenant_name": None,
        "reuse": True,
        "n_products": 42,
        "n_orders": 48,
        "n_buyers": 40,
    },
    {
        "idx": 2,
        "phone": "13900000201",
        "password": VOLUME_PASSWORD,
        "display_name": "演示·IP增长学院",
        "account_name": "演示·IP增长学院",
        "tag": "学院",
        "tenant_name": f"{TENANT_PREFIX}01",
        "reuse": False,
        "n_products": 36,
        "n_orders": 42,
        "n_buyers": 36,
    },
    {
        "idx": 3,
        "phone": "13900000202",
        "password": VOLUME_PASSWORD,
        "display_name": "演示·私域咨询社",
        "account_name": "演示·私域咨询社",
        "tag": "咨询",
        "tenant_name": f"{TENANT_PREFIX}02",
        "reuse": False,
        "n_products": 45,
        "n_orders": 40,
        "n_buyers": 42,
    },
    {
        "idx": 4,
        "phone": "13900000203",
        "password": VOLUME_PASSWORD,
        "display_name": "演示·资料工具店",
        "account_name": "演示·资料工具店",
        "tag": "资料",
        "tenant_name": f"{TENANT_PREFIX}03",
        "reuse": False,
        "n_products": 38,
        "n_orders": 44,
        "n_buyers": 38,
    },
]


def _stem(stems: list[str], i: int) -> str:
    if i < len(stems):
        return stems[i]
    return f"{stems[i % len(stems)]}·进阶{i // len(stems) + 1}"


def _vol_name(tag: str, stem: str) -> str:
    return f"{VOLUME_PREFIX}·{tag}·{stem}"


def _product_status(rank: int, total: int) -> str:
    """约 70% 在售，其余覆盖草稿/待审/下架/已审/驳回。"""
    if total <= 8:
        return "on_sale"
    if rank >= total - 1:
        return "rejected"
    if rank >= total - 3:
        return "approved"
    if rank >= total - 5:
        return "off_sale"
    if rank >= total - 8:
        return "pending_review"
    if rank >= total - 12:
        return "draft"
    return "on_sale"


def _order_status_plan(n: int) -> list[str]:
    """每家订单状态配比，总数 = n（30～50）。"""
    n_refunded = max(3, round(n * 0.08))
    n_refunding = max(2, round(n * 0.05))
    n_claim = max(2, round(n * 0.05))
    n_closed = max(3, round(n * 0.10))
    n_pend = max(4, round(n * 0.14))
    n_paid = n - n_refunded - n_refunding - n_claim - n_closed - n_pend
    if n_paid < 12:
        n_paid = 12
        extra = n_paid + n_refunded + n_refunding + n_claim + n_closed + n_pend - n
        n_pend = max(3, n_pend - extra)
    plan = (
        ["paid"] * n_paid
        + ["pending_payment"] * n_pend
        + ["closed"] * n_closed
        + ["refunded"] * n_refunded
        + ["refunding"] * n_refunding
        + ["claim_pending"] * n_claim
    )
    if len(plan) < n:
        plan.extend(["paid"] * (n - len(plan)))
    return plan[:n]


def _reset_volume(db) -> None:
    extra_tenants = db.query(Tenant).filter(Tenant.name.like(f"{TENANT_PREFIX}%")).all()
    extra_tids = [t.id for t in extra_tenants]
    vol_products = db.query(ShopProduct).filter(ShopProduct.name.like(f"{VOLUME_PREFIX}%")).all()
    pids = [p.id for p in vol_products]
    vol_orders = db.query(ShopOrder).filter(ShopOrder.order_no.like(f"{ORDER_PREFIX}%")).all()
    oids = [o.id for o in vol_orders]
    if extra_tids:
        extra_orders = db.query(ShopOrder).filter(ShopOrder.tenant_id.in_(extra_tids)).all()
        for o in extra_orders:
            if o.id not in oids:
                oids.append(o.id)
        extra_products = db.query(ShopProduct).filter(ShopProduct.tenant_id.in_(extra_tids)).all()
        for p in extra_products:
            if p.id not in pids:
                pids.append(p.id)

    if oids:
        eids = [
            e.id
            for e in db.query(ShopEntitlement).filter(ShopEntitlement.order_id.in_(oids)).all()
        ]
        if eids:
            db.query(ShopVerification).filter(ShopVerification.entitlement_id.in_(eids)).delete(
                synchronize_session=False
            )
            db.query(ShopBooking).filter(ShopBooking.entitlement_id.in_(eids)).delete(synchronize_session=False)
            db.query(ShopLessonProgress).filter(ShopLessonProgress.entitlement_id.in_(eids)).delete(
                synchronize_session=False
            )
            db.query(ShopDigitalDownload).filter(ShopDigitalDownload.entitlement_id.in_(eids)).delete(
                synchronize_session=False
            )
            db.query(ShopEnrollment).filter(ShopEnrollment.entitlement_id.in_(eids)).delete(
                synchronize_session=False
            )
            db.query(ShopEntitlement).filter(ShopEntitlement.id.in_(eids)).delete(synchronize_session=False)
        db.query(ShopRefund).filter(ShopRefund.order_id.in_(oids)).delete(synchronize_session=False)
        db.query(ShopPaymentLog).filter(ShopPaymentLog.order_id.in_(oids)).delete(synchronize_session=False)
        db.query(ShopPayment).filter(ShopPayment.order_id.in_(oids)).delete(synchronize_session=False)
        db.query(ShopInvoiceRequest).filter(ShopInvoiceRequest.order_id.in_(oids)).delete(synchronize_session=False)
        db.query(ShopSettlementItem).filter(ShopSettlementItem.order_id.in_(oids)).delete(synchronize_session=False)
        db.query(ShopClaimToken).filter(ShopClaimToken.order_id.in_(oids)).delete(synchronize_session=False)
        db.query(ShopModerationCase).filter(ShopModerationCase.order_id.in_(oids)).delete(synchronize_session=False)
        db.query(ShopOrder).filter(ShopOrder.id.in_(oids)).delete(synchronize_session=False)
    if pids:
        db.query(ShopProductReview).filter(ShopProductReview.product_id.in_(pids)).delete(synchronize_session=False)
        db.query(ShopChannelMapping).filter(ShopChannelMapping.product_id.in_(pids)).delete(synchronize_session=False)
        db.query(ShopChannelAuditLog).filter(ShopChannelAuditLog.product_id.in_(pids)).delete(synchronize_session=False)
        db.query(ShopModerationCase).filter(ShopModerationCase.product_id.in_(pids)).delete(synchronize_session=False)
        db.query(ShopProduct).filter(ShopProduct.id.in_(pids)).delete(synchronize_session=False)

    vol_cols = db.query(ShopColumn).filter(ShopColumn.title.like(f"{VOLUME_PREFIX}%")).all()
    cids = [c.id for c in vol_cols]
    if extra_tids:
        extra_cols = db.query(ShopColumn).filter(ShopColumn.tenant_id.in_(extra_tids)).all()
        for c in extra_cols:
            if c.id not in cids:
                cids.append(c.id)
    if cids:
        db.query(ShopLesson).filter(ShopLesson.column_id.in_(cids)).delete(synchronize_session=False)
        db.query(ShopColumn).filter(ShopColumn.id.in_(cids)).delete(synchronize_session=False)

    vol_pkgs = db.query(ShopDigitalPackage).filter(ShopDigitalPackage.title.like(f"{VOLUME_PREFIX}%")).all()
    pkg_ids = [p.id for p in vol_pkgs]
    if extra_tids:
        extra_pkgs = db.query(ShopDigitalPackage).filter(ShopDigitalPackage.tenant_id.in_(extra_tids)).all()
        for p in extra_pkgs:
            if p.id not in pkg_ids:
                pkg_ids.append(p.id)
    if pkg_ids:
        db.query(ShopDigitalAsset).filter(ShopDigitalAsset.package_id.in_(pkg_ids)).delete(synchronize_session=False)
        db.query(ShopDigitalPackage).filter(ShopDigitalPackage.id.in_(pkg_ids)).delete(synchronize_session=False)

    vol_offers = db.query(ShopServiceOffer).filter(ShopServiceOffer.title.like(f"{VOLUME_PREFIX}%")).all()
    offer_ids = [o.id for o in vol_offers]
    if extra_tids:
        extra_offers = db.query(ShopServiceOffer).filter(ShopServiceOffer.tenant_id.in_(extra_tids)).all()
        for o in extra_offers:
            if o.id not in offer_ids:
                offer_ids.append(o.id)
    if offer_ids:
        db.query(ShopServiceSlot).filter(ShopServiceSlot.service_offer_id.in_(offer_ids)).delete(
            synchronize_session=False
        )
        db.query(ShopServiceOffer).filter(ShopServiceOffer.id.in_(offer_ids)).delete(synchronize_session=False)

    db.query(ShopBuyer).filter(ShopBuyer.wx_openid.like(f"{BUYER_OPENID_PREFIX}%")).delete(synchronize_session=False)
    db.query(ShopSettlementBatch).filter(ShopSettlementBatch.batch_no.like(f"{ORDER_PREFIX}SET%")).delete(
        synchronize_session=False
    )
    db.query(ShopMerchantServiceLog).filter(ShopMerchantServiceLog.content.like("验收演示%")).delete(
        synchronize_session=False
    )
    db.query(ShopAuditLog).filter(ShopAuditLog.summary.like("验收演示%")).delete(synchronize_session=False)
    db.query(ShopSmsLog).filter(ShopSmsLog.content.like("验收演示%")).delete(synchronize_session=False)
    db.query(ShopModerationCase).filter(ShopModerationCase.case_no.like(f"{ORDER_PREFIX}MC%")).delete(
        synchronize_session=False
    )
    db.query(ShopPlatformCategory).filter(ShopPlatformCategory.code.like("vol.cat.%")).delete(
        synchronize_session=False
    )
    vol_tags = db.query(ShopMerchantTag).filter(ShopMerchantTag.name.like(f"{VOLUME_PREFIX}%")).all()
    tag_ids = [t.id for t in vol_tags]
    if tag_ids:
        db.query(ShopMerchantTagLink).filter(ShopMerchantTagLink.tag_id.in_(tag_ids)).delete(
            synchronize_session=False
        )
        db.query(ShopMerchantTag).filter(ShopMerchantTag.id.in_(tag_ids)).delete(synchronize_session=False)
    if extra_tids:
        db.query(ShopBuyer).filter(ShopBuyer.tenant_id.in_(extra_tids)).delete(synchronize_session=False)
        db.query(ShopMerchantSubscription).filter(ShopMerchantSubscription.tenant_id.in_(extra_tids)).delete(
            synchronize_session=False
        )
        db.query(ShopPaymentOnboarding).filter(ShopPaymentOnboarding.tenant_id.in_(extra_tids)).delete(
            synchronize_session=False
        )
        db.query(ShopChannelSetting).filter(ShopChannelSetting.tenant_id.in_(extra_tids)).delete(
            synchronize_session=False
        )
        db.query(ShopClaimToken).filter(ShopClaimToken.tenant_id.in_(extra_tids)).delete(synchronize_session=False)
    db.flush()
    print("reset-volume: cleared 演示量 catalog / DEMOVOL orders / QA_DEMO_验收 extra rows")


def _ensure_column(db, *, tenant_id, shop_id, user_id, title: str) -> ShopColumn:
    row = (
        db.query(ShopColumn)
        .filter(uuid_eq(ShopColumn.tenant_id, tenant_id), ShopColumn.title == title)
        .first()
    )
    if row:
        return row
    row = ShopColumn(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        shop_id=shop_id,
        title=title,
        intro="验收演示专栏",
        status="published",
        created_by=user_id,
    )
    db.add(row)
    db.flush()
    db.add(
        ShopLesson(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            column_id=row.id,
            title="第 1 讲 · 开场",
            media_type="video",
            media_url="https://example.com/demo-lesson.mp4",
            duration_sec=180,
            is_trial=True,
            trial_seconds=20,
            sort_order=1,
            status="published",
        )
    )
    db.add(
        ShopLesson(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            column_id=row.id,
            title="第 2 讲 · 实操",
            media_type="video",
            media_url="https://example.com/demo-lesson-2.mp4",
            duration_sec=420,
            is_trial=False,
            sort_order=2,
            status="published",
        )
    )
    db.flush()
    return row


def _ensure_package(db, *, tenant_id, shop_id, user_id, title: str) -> ShopDigitalPackage:
    row = (
        db.query(ShopDigitalPackage)
        .filter(uuid_eq(ShopDigitalPackage.tenant_id, tenant_id), ShopDigitalPackage.title == title)
        .first()
    )
    if row:
        return row
    row = ShopDigitalPackage(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        shop_id=shop_id,
        title=title,
        deliver_mode="download",
        max_downloads=5,
        status="published",
        created_by=user_id,
    )
    db.add(row)
    db.flush()
    db.add(
        ShopDigitalAsset(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            package_id=row.id,
            file_id=f"vol-{uuid.uuid4().hex[:12]}",
            file_name=f"{title}.pdf",
            file_url="/storage/demo/volume.pdf",
            mime="application/pdf",
            size_bytes=2048,
            previewable=True,
            sort_order=1,
        )
    )
    db.flush()
    return row


def _ensure_offer(db, *, tenant_id, shop_id, user_id, title: str, times: int) -> ShopServiceOffer:
    row = (
        db.query(ShopServiceOffer)
        .filter(uuid_eq(ShopServiceOffer.tenant_id, tenant_id), ShopServiceOffer.title == title)
        .first()
    )
    if row:
        return row
    row = ShopServiceOffer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        shop_id=shop_id,
        title=title,
        mode="times_card",
        status="published",
        total_times=times,
        valid_days=90,
        duration_minutes=60,
        created_by=user_id,
    )
    db.add(row)
    db.flush()
    return row


def _ensure_review(db, product: ShopProduct, *, manual: str, auto: str = "pass", reason: str | None = None) -> None:
    existing = (
        db.query(ShopProductReview)
        .filter(uuid_eq(ShopProductReview.product_id, product.id))
        .order_by(ShopProductReview.created_at.desc())
        .first()
    )
    now = _now()
    if existing:
        existing.manual_result = manual
        existing.auto_result = auto
        if reason:
            existing.reject_reason = reason
        if manual in ("approved", "rejected"):
            existing.reviewed_at = existing.reviewed_at or now
        product.last_review_id = existing.id
        return
    review = ShopProductReview(
        id=uuid.uuid4(),
        product_id=product.id,
        tenant_id=product.tenant_id,
        snapshot_json={"name": product.name, "type": product.type, "price_cents": product.price_cents},
        auto_result=auto,
        auto_flags=[{"code": "demo_flag", "message": "验收演示机审标记"}] if auto == "flag" else [],
        manual_result=manual,
        reject_reason=reason,
        submitted_by=product.created_by,
        reviewed_at=now if manual in ("approved", "rejected") else None,
    )
    db.add(review)
    db.flush()
    product.last_review_id = review.id


def _ensure_product(
    db,
    *,
    tenant_id,
    shop_id,
    user_id,
    ptype: str,
    name: str,
    price: int,
    ref_type: str,
    ref_id,
    status: str,
    extra: dict,
) -> ShopProduct:
    row = (
        db.query(ShopProduct)
        .filter(uuid_eq(ShopProduct.tenant_id, tenant_id), ShopProduct.name == name)
        .first()
    )
    if row:
        row.status = status
        row.price_cents = price
        row.ref_type = ref_type
        row.ref_id = ref_id
        row.extra = extra
        if status in ("on_sale", "off_sale", "approved") and not row.last_review_id:
            row.last_review_id = uuid.uuid4()
        db.flush()
        return row
    row = ShopProduct(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        shop_id=shop_id,
        type=ptype,
        name=name,
        subtitle=f"验收演示 · {ptype}",
        price_cents=price,
        line_price_cents=price * 2 if ptype == "course" else None,
        status=status,
        ref_type=ref_type,
        ref_id=ref_id,
        last_review_id=uuid.uuid4() if status in ("on_sale", "off_sale", "approved") else None,
        refund_policy="before_fulfill",
        extra=extra,
        created_by=user_id,
    )
    db.add(row)
    db.flush()
    return row


def _catalog_volume(db, merchant: ShopMerchantAccount, shop: ShopStore, user: User, spec: dict, rng: random.Random) -> list[ShopProduct]:
    n = spec["n_products"]
    tag = spec["tag"]
    n_course = max(12, round(n * 0.40))
    n_digital = max(10, round(n * 0.30))
    n_service = n - n_course - n_digital
    if n_service < 8:
        n_service = 8
        n_course = n - n_digital - n_service
    specs: list[tuple[str, str]] = (
        [("course", _stem(COURSE_STEMS, i)) for i in range(n_course)]
        + [("digital", _stem(DIGITAL_STEMS, i)) for i in range(n_digital)]
        + [("service", _stem(SERVICE_STEMS, i)) for i in range(n_service)]
    )
    rng.shuffle(specs)
    products: list[ShopProduct] = []
    for rank, (ptype, stem) in enumerate(specs):
        name = _vol_name(tag, stem)
        status = _product_status(rank, len(specs))
        price = [9900, 19900, 29900, 39900, 49900, 59900, 79900][rank % 7]
        extra: dict = {"intro": f"{stem}（验收演示）"}
        if ptype == "course":
            col = _ensure_column(
                db,
                tenant_id=merchant.tenant_id,
                shop_id=shop.id,
                user_id=user.id,
                title=_vol_name(tag, f"专栏·{stem}"),
            )
            extra["lesson_count"] = 2
            ref_type, ref_id = "column", col.id
            price = 19900 + (rank % 5) * 10000
        elif ptype == "digital":
            pkg = _ensure_package(
                db,
                tenant_id=merchant.tenant_id,
                shop_id=shop.id,
                user_id=user.id,
                title=_vol_name(tag, f"资料包·{stem}"),
            )
            ref_type, ref_id = "digital_package", pkg.id
            price = 2900 + (rank % 6) * 2000
        else:
            times = 3 + (rank % 3)
            offer = _ensure_offer(
                db,
                tenant_id=merchant.tenant_id,
                shop_id=shop.id,
                user_id=user.id,
                title=_vol_name(tag, f"服务·{stem}"),
                times=times,
            )
            extra["service_times"] = times
            ref_type, ref_id = "service_offer", offer.id
            price = 39900 + (rank % 4) * 20000
        product = _ensure_product(
            db,
            tenant_id=merchant.tenant_id,
            shop_id=shop.id,
            user_id=user.id,
            ptype=ptype,
            name=name,
            price=price,
            ref_type=ref_type,
            ref_id=ref_id,
            status=status,
            extra=extra,
        )
        if status == "pending_review":
            auto = "flag" if rank % 2 == 0 else "pass"
            _ensure_review(db, product, manual="pending", auto=auto)
        elif status == "rejected":
            _ensure_review(db, product, manual="rejected", auto="pass", reason="验收演示：标题需补充适用人群")
        elif status in ("approved", "on_sale", "off_sale"):
            _ensure_review(db, product, manual="approved", auto="pass")
        products.append(product)
    db.flush()
    return products


def _ensure_buyer(db, *, tenant_id, idx: int, seq: int) -> ShopBuyer:
    openid = f"{BUYER_OPENID_PREFIX}{idx:02d}_{seq:03d}"
    mobile = f"137{idx:02d}{seq:06d}"
    row = (
        db.query(ShopBuyer)
        .filter(uuid_eq(ShopBuyer.tenant_id, tenant_id), ShopBuyer.wx_openid == openid)
        .first()
    )
    if row:
        if not row.mobile:
            row.mobile = mobile
        return row
    clash = (
        db.query(ShopBuyer)
        .filter(uuid_eq(ShopBuyer.tenant_id, tenant_id), ShopBuyer.mobile == mobile)
        .first()
    )
    if clash:
        return clash
    row = ShopBuyer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        mobile=mobile,
        wx_openid=openid,
        nickname=f"演示买家{idx:02d}-{seq:02d}",
    )
    db.add(row)
    db.flush()
    return row


def _ensure_order(
    db,
    *,
    no: str,
    tenant_id,
    shop_id,
    buyer: ShopBuyer,
    product: ShopProduct,
    status: str,
    created_at: datetime,
    rng: random.Random,
) -> ShopOrder:
    from app.services.shop.order_service import _activate_entitlement_for_order

    row = db.query(ShopOrder).filter(ShopOrder.order_no == no).first()
    snap = {
        "id": str(product.id),
        "name": product.name,
        "type": product.type,
        "price_cents": product.price_cents,
        "ref_type": product.ref_type,
        "ref_id": str(product.ref_id) if product.ref_id else None,
        "extra": product.extra or {},
    }
    paid_at = created_at + timedelta(minutes=rng.randint(2, 90)) if status != "pending_payment" else None
    if row is None:
        row = ShopOrder(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            shop_id=shop_id,
            buyer_id=buyer.id,
            product_id=product.id,
            product_snapshot_json=snap,
            order_no=no,
            type=product.type,
            amount_cents=product.price_cents,
            status="pending_payment" if status in ("refunded", "refunding") else status,
            source="public_douyin" if status == "claim_pending" else "private",
            buyer_mobile_snapshot=buyer.mobile,
            claim_token=f"demo_vol_claim_{no[-8:]}" if status == "claim_pending" else None,
            claim_expires_at=(_now() + timedelta(days=7)) if status == "claim_pending" else None,
            created_at=created_at,
        )
        db.add(row)
        db.flush()
        pay = ShopPayment(
            id=uuid.uuid4(),
            order_id=row.id,
            tenant_id=tenant_id,
            shop_id=shop_id,
            amount_cents=product.price_cents,
            status="pending",
            created_at=created_at,
        )
        db.add(pay)
        db.flush()
    else:
        pay = db.query(ShopPayment).filter(uuid_eq(ShopPayment.order_id, row.id)).first()

    if status in ("paid", "refunded", "refunding"):
        row.status = "paid"
        row.paid_amount_cents = product.price_cents
        row.paid_at = paid_at or _now()
        row.paid_channel = "stub"
        row.wx_transaction_id = row.wx_transaction_id or f"VOLTX{no[-12:]}"
        if pay:
            pay.status = "success"
            pay.paid_at = row.paid_at
            pay.wx_transaction_id = row.wx_transaction_id
        _activate_entitlement_for_order(db, row)
        db.flush()
    elif status == "closed":
        row.status = "closed"
    elif status == "claim_pending":
        row.status = "claim_pending"
        row.source = "public_douyin"
        row.claim_token = row.claim_token or f"demo_vol_claim_{no[-8:]}"
        row.claim_expires_at = row.claim_expires_at or (_now() + timedelta(days=7))
    elif status == "pending_payment":
        row.status = "pending_payment"

    if status in ("refunded", "refunding"):
        _ensure_refund(db, row, succeeded=(status == "refunded"), created_at=paid_at or created_at)
    db.flush()
    return row


def _ensure_refund(db, order: ShopOrder, *, succeeded: bool, created_at: datetime) -> None:
    existing = db.query(ShopRefund).filter(uuid_eq(ShopRefund.order_id, order.id)).first()
    now = created_at + timedelta(hours=6)
    if existing is None:
        existing = ShopRefund(
            id=uuid.uuid4(),
            order_id=order.id,
            tenant_id=order.tenant_id,
            amount_cents=order.amount_cents,
            reason="验收演示退款",
            status="processing",
            initiated_by="buyer",
            created_at=now,
        )
        db.add(existing)
        db.flush()
    if succeeded:
        existing.status = "succeeded"
        existing.processed_at = now + timedelta(hours=2)
        existing.wx_refund_id = existing.wx_refund_id or f"RF{uuid.uuid4().hex[:16]}"
        order.status = "refunded"
        order.refund_amount_cents = order.amount_cents
        order.refunded_at = existing.processed_at
        order.refund_reason = existing.reason
        ent = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.order_id, order.id)).first()
        if ent and ent.status != "revoked":
            ent.status = "revoked"
            ent.revoked_at = existing.processed_at
            ent.revoke_reason = "退款撤销"
            existing.entitlement_revoked_at = existing.processed_at
            for enr in (
                db.query(ShopEnrollment)
                .filter(uuid_eq(ShopEnrollment.entitlement_id, ent.id), ShopEnrollment.status == "active")
                .all()
            ):
                enr.status = "revoked"
    else:
        existing.status = "processing"
        order.status = "refunding"


def _ensure_invoices(db, orders: list[ShopOrder], rng: random.Random) -> None:
    paid = [o for o in orders if o.status == "paid"]
    for i, order in enumerate(paid):
        row = db.query(ShopInvoiceRequest).filter(uuid_eq(ShopInvoiceRequest.order_id, order.id)).first()
        status = ["issued", "submitted", "rejected"][i % 3] if i >= 3 else ("issued" if i % 4 == 0 else "submitted")
        if row is None:
            company = i % 3 == 1
            row = ShopInvoiceRequest(
                id=uuid.uuid4(),
                tenant_id=order.tenant_id,
                shop_id=order.shop_id,
                buyer_id=order.buyer_id,
                order_id=order.id,
                invoice_type="normal",
                title_type="company" if company else "person",
                title="验收演示科技有限公司" if company else f"验收演示个人{i+1:02d}",
                tax_no="91110000MADEMO001X" if company else None,
                email="demo@example.com",
                amount_cents=order.paid_amount_cents or order.amount_cents,
                status=status,
                reject_reason="验收演示：抬头与主体不一致" if status == "rejected" else None,
            )
            db.add(row)
        row.status = status
        order.invoice_status = "none" if status == "rejected" else status
        if status == "issued":
            row.issued_at = row.issued_at or _now()
            row.invoice_no = row.invoice_no or f"INV{order.order_no[-10:]}"
            row.reject_reason = None
    db.flush()


def _ensure_settlement(db, *, merchant: ShopMerchantAccount, shop: ShopStore, orders: list[ShopOrder], idx: int) -> None:
    paid = [o for o in orders if o.status == "paid" and o.paid_at]
    if not paid:
        return
    now = _now()
    n_batches = min(10, max(6, (len(paid) + 2) // 3))
    chunks: list[list[ShopOrder]] = [[] for _ in range(n_batches)]
    for i, o in enumerate(paid):
        chunks[i % n_batches].append(o)
    statuses = ["paid", "pending", "closed", "payment_failed"]
    for bidx, group in enumerate(chunks, start=1):
        if not group:
            continue
        batch_no = f"{ORDER_PREFIX}SET{idx:02d}{bidx:02d}"
        existing = db.query(ShopSettlementBatch).filter(ShopSettlementBatch.batch_no == batch_no).first()
        if existing:
            continue
        gross = sum(int(o.paid_amount_cents or o.amount_cents or 0) for o in group)
        fee = gross * 6 // 1000
        net = gross - fee
        st = statuses[(bidx - 1) % len(statuses)]
        if st == "closed" and net > 0:
            st = "paid"
        start = (now - timedelta(days=7 * (n_batches - bidx + 2))).date()
        end = start + timedelta(days=6)
        batch = ShopSettlementBatch(
            id=uuid.uuid4(),
            tenant_id=merchant.tenant_id,
            shop_id=shop.id,
            batch_no=batch_no,
            period_start=start,
            period_end=end,
            gross_amount_cents=gross,
            platform_fee_cents=fee,
            refund_reversal_cents=0,
            opening_balance_cents=0,
            period_net_cents=net,
            net_amount_cents=net,
            status=st,
            paid_at=now - timedelta(days=3) if st == "paid" else None,
        )
        db.add(batch)
        db.flush()
        for o in group:
            db.add(
                ShopSettlementItem(
                    id=uuid.uuid4(),
                    batch_id=batch.id,
                    item_type="order_income",
                    order_id=o.id,
                    amount_cents=int(o.paid_amount_cents or o.amount_cents or 0),
                    fee_cents=int(o.paid_amount_cents or o.amount_cents or 0) * 6 // 1000,
                )
            )
            o.settled_at = o.settled_at or now - timedelta(days=3)
    db.flush()


def _ensure_mappings(db, products: list[ShopProduct], shop: ShopStore) -> None:
    on_sale = [p for p in products if p.status == "on_sale"]
    for i, p in enumerate(on_sale):
        ch_pid = f"vol_doudian_{str(p.id).replace('-', '')[:16]}"
        row = (
            db.query(ShopChannelMapping)
            .filter(
                uuid_eq(ShopChannelMapping.tenant_id, p.tenant_id),
                ShopChannelMapping.channel == "douyin",
                ShopChannelMapping.channel_product_id == ch_pid,
            )
            .first()
        )
        if row:
            continue
        audit = ["approved", "pending", "rejected"][i % 3]
        db.add(
            ShopChannelMapping(
                id=uuid.uuid4(),
                tenant_id=p.tenant_id,
                shop_id=shop.id,
                product_id=p.id,
                channel="douyin",
                channel_product_id=ch_pid,
                channel_product_url=f"https://example.com/douyin/{ch_pid}",
                combo="1A" if i % 2 == 0 else "1B",
                status="mapped" if audit != "rejected" else "blocked",
                external_audit_status=audit,
                mount_blocked_reason="验收演示：未过挂载闸" if audit == "rejected" else None,
            )
        )
    db.flush()


def _fill_extra_content(db, *, merchant, shop, user, spec: dict) -> None:
    tag = spec["tag"]

    def _need(model, field, like: str) -> int:
        cur = (
            db.query(model)
            .filter(uuid_eq(model.tenant_id, merchant.tenant_id), field.like(like))
            .count()
        )
        return max(0, LIST_TARGET - int(cur))

    n_col = _need(ShopColumn, ShopColumn.title, f"{VOLUME_PREFIX}%")
    n_pkg = _need(ShopDigitalPackage, ShopDigitalPackage.title, f"{VOLUME_PREFIX}%")
    n_off = _need(ShopServiceOffer, ShopServiceOffer.title, f"{VOLUME_PREFIX}%")
    for i in range(1, max(n_col, n_pkg, n_off) + 1):
        st = "published" if i <= LIST_TARGET - 8 else "draft"
        if i <= n_col:
            col = _ensure_column(
                db,
                tenant_id=merchant.tenant_id,
                shop_id=shop.id,
                user_id=user.id,
                title=_vol_name(tag, f"专栏补{i:02d}"),
            )
            col.status = st
        if i <= n_pkg:
            pkg = _ensure_package(
                db,
                tenant_id=merchant.tenant_id,
                shop_id=shop.id,
                user_id=user.id,
                title=_vol_name(tag, f"资料补{i:02d}"),
            )
            pkg.status = st
        if i <= n_off:
            offer = _ensure_offer(
                db,
                tenant_id=merchant.tenant_id,
                shop_id=shop.id,
                user_id=user.id,
                title=_vol_name(tag, f"服务补{i:02d}"),
                times=3 + (i % 3),
            )
            offer.status = st
            if (
                db.query(ShopServiceSlot)
                .filter(uuid_eq(ShopServiceSlot.service_offer_id, offer.id))
                .first()
                is None
            ):
                start = _now() + timedelta(days=i % 14, hours=10)
                db.add(
                    ShopServiceSlot(
                        id=uuid.uuid4(),
                        tenant_id=merchant.tenant_id,
                        shop_id=shop.id,
                        service_offer_id=offer.id,
                        start_at=start,
                        end_at=start + timedelta(minutes=60),
                        capacity=4,
                        booked_count=0,
                        status="open",
                    )
                )
    db.flush()


def _fill_bookings_and_verify(db, *, merchant, shop, user, rng: random.Random) -> None:
    ents = (
        db.query(ShopEntitlement)
        .filter(uuid_eq(ShopEntitlement.tenant_id, merchant.tenant_id), ShopEntitlement.status == "active")
        .all()
    )
    service_ents = []
    for e in ents:
        p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, e.product_id)).first()
        if p and p.type == "service":
            service_ents.append(e)
    if not service_ents:
        return
    per = max(1, (LIST_TARGET + len(service_ents) - 1) // len(service_ents))
    slots = ["09:00-10:00", "10:00-11:00", "14:00-15:00", "15:00-16:00", "16:00-17:00"]
    created = 0
    for e in service_ents:
        for j in range(per):
            if created >= LIST_TARGET + 8:
                break
            booked_date = (_now() - timedelta(days=2 + j * 3)).date()
            slot_label = slots[j % len(slots)]
            hit = (
                db.query(ShopBooking)
                .filter(
                    uuid_eq(ShopBooking.entitlement_id, e.id),
                    ShopBooking.booked_date == booked_date,
                    ShopBooking.booked_time_slot == slot_label,
                )
                .first()
            )
            if hit is None:
                st = ["booked", "completed", "cancelled"][j % 3]
                hit = ShopBooking(
                    id=uuid.uuid4(),
                    tenant_id=merchant.tenant_id,
                    shop_id=shop.id,
                    buyer_id=e.buyer_id,
                    entitlement_id=e.id,
                    service_product_id=e.product_id,
                    status=st,
                    booked_date=booked_date,
                    booked_time_slot=slot_label,
                    cancel_reason="验收演示取消" if st == "cancelled" else None,
                    cancelled_at=_now() if st == "cancelled" else None,
                )
                db.add(hit)
                db.flush()
            created += 1
            if hit.status != "cancelled":
                key = f"vol-vf-{str(e.id).replace('-', '')[:10]}-{j}"
                if db.query(ShopVerification).filter(ShopVerification.idempotency_key == key).first():
                    continue
                db.add(
                    ShopVerification(
                        id=uuid.uuid4(),
                        tenant_id=merchant.tenant_id,
                        shop_id=shop.id,
                        buyer_id=e.buyer_id,
                        entitlement_id=e.id,
                        booking_id=hit.id if hit.status == "completed" else None,
                        type="times_card_deduct",
                        status="success",
                        operator_id=user.id,
                        verify_code=e.verify_code,
                        idempotency_key=key,
                        deducted_count=1,
                    )
                )
                if e.remaining_count is not None and e.remaining_count > 0:
                    e.remaining_count = max(0, int(e.remaining_count) - 1)
    db.flush()


def _fill_progress_and_downloads(db, *, merchant) -> None:
    ents = (
        db.query(ShopEntitlement)
        .filter(uuid_eq(ShopEntitlement.tenant_id, merchant.tenant_id), ShopEntitlement.status == "active")
        .all()
    )
    for e in ents:
        p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, e.product_id)).first()
        if not p:
            continue
        if p.type == "course" and p.ref_id:
            lessons = (
                db.query(ShopLesson)
                .filter(uuid_eq(ShopLesson.column_id, p.ref_id), ShopLesson.deleted_at.is_(None))
                .all()
            )
            for les in lessons:
                hit = (
                    db.query(ShopLessonProgress)
                    .filter(
                        uuid_eq(ShopLessonProgress.entitlement_id, e.id),
                        uuid_eq(ShopLessonProgress.lesson_id, les.id),
                    )
                    .first()
                )
                if hit:
                    continue
                db.add(
                    ShopLessonProgress(
                        id=uuid.uuid4(),
                        tenant_id=merchant.tenant_id,
                        buyer_id=e.buyer_id,
                        entitlement_id=e.id,
                        course_id=p.ref_id,
                        lesson_id=les.id,
                        position_sec=30,
                        progress_pct=20 if les.is_trial else 55,
                        last_learned_at=_now(),
                    )
                )
        if p.type == "digital" and p.ref_id:
            assets = db.query(ShopDigitalAsset).filter(uuid_eq(ShopDigitalAsset.package_id, p.ref_id)).all()
            for a in assets:
                hit = (
                    db.query(ShopDigitalDownload)
                    .filter(
                        uuid_eq(ShopDigitalDownload.entitlement_id, e.id),
                        ShopDigitalDownload.file_id == a.file_id,
                    )
                    .first()
                )
                if hit:
                    continue
                db.add(
                    ShopDigitalDownload(
                        id=uuid.uuid4(),
                        tenant_id=merchant.tenant_id,
                        buyer_id=e.buyer_id,
                        entitlement_id=e.id,
                        file_id=a.file_id,
                        download_count=1 + (hash(a.file_id) % 3),
                    )
                )
    db.flush()


def _ensure_approved_onboarding(db, *, merchant: ShopMerchantAccount, user: User) -> uuid.UUID | None:
    if merchant.onboarding_application_id:
        return merchant.onboarding_application_id
    app = (
        db.query(ShopOnboardingApplication)
        .filter(
            uuid_eq(ShopOnboardingApplication.tenant_id, merchant.tenant_id),
            ShopOnboardingApplication.status == "approved",
        )
        .order_by(ShopOnboardingApplication.reviewed_at.desc())
        .first()
    )
    if app is None:
        now = _now()
        app = ShopOnboardingApplication(
            id=uuid.uuid4(),
            application_no=_code(db, "shop_onboarding", f"DEMVOL{str(merchant.merchant_no or '000000')[-6:]}"),
            tenant_id=merchant.tenant_id,
            entity_type=merchant.entity_type or "enterprise",
            initiator="ops_assisted",
            status="approved",
            legal_name=merchant.legal_name or merchant.display_name,
            display_name=merchant.display_name,
            contact_name=merchant.contact_name,
            contact_mobile=merchant.contact_mobile,
            qualification_files={},
            reviewed_at=now,
            submitted_at=now - timedelta(days=7),
        )
        db.add(app)
        db.flush()
    merchant.onboarding_application_id = app.id
    if not merchant.onboarding_approved_at:
        merchant.onboarding_approved_at = app.reviewed_at or _now()
    db.flush()
    return app.id


def _fill_service_logs(db, *, merchant, operator_id, spec: dict) -> None:
    if not operator_id:
        return
    n = (
        db.query(ShopMerchantServiceLog)
        .filter(uuid_eq(ShopMerchantServiceLog.merchant_id, merchant.id))
        .filter(ShopMerchantServiceLog.content.like("验收演示%"))
        .count()
    )
    types = ["call", "visit", "wechat", "note", "training", "onboarding_assist", "email", "complaint"]
    statuses = ["logged", "logged", "pending", "done"]
    app_id = merchant.onboarding_application_id
    if not app_id:
        app = (
            db.query(ShopOnboardingApplication)
            .filter(
                uuid_eq(ShopOnboardingApplication.tenant_id, merchant.tenant_id),
                ShopOnboardingApplication.status == "approved",
            )
            .order_by(ShopOnboardingApplication.reviewed_at.desc())
            .first()
        )
        app_id = app.id if app else None
    for i in range(n + 1, LIST_TARGET + 1):
        log_type = types[(i - 1) % len(types)]
        related_oid = None
        if log_type == "onboarding_assist":
            if app_id:
                related_oid = app_id
            else:
                log_type = "note"
        db.add(
            ShopMerchantServiceLog(
                id=uuid.uuid4(),
                merchant_id=merchant.id,
                tenant_id=merchant.tenant_id,
                type=log_type,
                status=statuses[(i - 1) % len(statuses)],
                content=f"验收演示跟进{spec['tag']}·{i:02d}：电话沟通套餐与上架进度。",
                payload_json={"demo": True, "seq": i},
                operator_user_id=operator_id,
                related_onboarding_id=related_oid,
                created_at=_now() - timedelta(days=i),
            )
        )
    db.flush()


def _fill_audit_logs(db, *, merchant, operator_id, spec: dict) -> None:
    n = (
        db.query(ShopAuditLog)
        .filter(uuid_eq(ShopAuditLog.tenant_id, merchant.tenant_id))
        .filter(ShopAuditLog.summary.like("验收演示%"))
        .count()
    )
    actions = ["merchant.suspend", "merchant.resume", "tag.edit", "manager.assign", "subscription.open", "reveal.mobile"]
    for i in range(n + 1, LIST_TARGET + 1):
        db.add(
            ShopAuditLog(
                id=uuid.uuid4(),
                tenant_id=merchant.tenant_id,
                merchant_id=merchant.id,
                action=actions[(i - 1) % len(actions)],
                summary=f"验收演示操作日志{spec['tag']}·{i:02d}",
                operator_user_id=operator_id,
                operator_name="演示·商家管家",
                source="seed",
                created_at=_now() - timedelta(days=i, hours=2),
            )
        )
    db.flush()


def _fill_sms_logs(db, *, merchant, shop, buyers: list[ShopBuyer]) -> None:
    n = (
        db.query(ShopSmsLog)
        .filter(uuid_eq(ShopSmsLog.tenant_id, merchant.tenant_id), ShopSmsLog.content.like("验收演示%"))
        .count()
    )
    types = ["claim_link", "pay_success", "refund", "verify_code", "booking"]
    statuses = ["sent", "sent", "failed"]
    for i in range(n + 1, LIST_TARGET + 1):
        buyer = buyers[(i - 1) % len(buyers)] if buyers else None
        db.add(
            ShopSmsLog(
                id=uuid.uuid4(),
                tenant_id=merchant.tenant_id,
                shop_id=shop.id,
                buyer_mobile=buyer.mobile if buyer and buyer.mobile else f"1370000{i:04d}"[-11:],
                type=types[(i - 1) % len(types)],
                content=f"验收演示短信{i:02d}：您的订单/领权通知。",
                status=statuses[(i - 1) % len(statuses)],
                provider_msg_id=f"VOLSMS{i:04d}",
                sent_at=_now() - timedelta(days=i % 20),
            )
        )
    db.flush()


def _fill_moderation(db, *, merchant, shop, products: list[ShopProduct], orders: list[ShopOrder], spec: dict) -> None:
    n = (
        db.query(ShopModerationCase)
        .filter(uuid_eq(ShopModerationCase.tenant_id, merchant.tenant_id))
        .filter(ShopModerationCase.case_no.like(f"{ORDER_PREFIX}MC{spec['idx']}%"))
        .count()
    )
    types = ["sensitive_word", "product_violation", "buyer_complaint", "user_report", "manual"]
    sources = ["f6_auto", "buyer", "ops", "external"]
    statuses = ["pending", "processing", "closed", "pending"]
    for i in range(n + 1, LIST_TARGET + 1):
        case_no = f"{ORDER_PREFIX}MC{spec['idx']}{i:03d}"
        if db.query(ShopModerationCase).filter(ShopModerationCase.case_no == case_no).first():
            continue
        p = products[(i - 1) % len(products)] if products else None
        o = orders[(i - 1) % len(orders)] if orders else None
        st = statuses[(i - 1) % len(statuses)]
        db.add(
            ShopModerationCase(
                id=uuid.uuid4(),
                case_no=case_no,
                tenant_id=merchant.tenant_id,
                shop_id=shop.id,
                case_type=types[(i - 1) % len(types)],
                object_type="product" if p else "order",
                object_ref=(p.name if p else (o.order_no if o else case_no))[:200],
                product_id=p.id if p else None,
                order_id=o.id if o and i % 4 == 0 else None,
                source=sources[(i - 1) % len(sources)],
                status=st,
                conclusion="验收演示结案：已下架整改" if st == "closed" else None,
                closed_at=_now() - timedelta(days=1) if st == "closed" else None,
                timeline_json=[{"at": _now().isoformat(), "event": "seed", "text": "验收演示工单"}],
            )
        )
    db.flush()


def _fill_payment_and_channel(db, *, merchant, shop, user) -> None:
    po = (
        db.query(ShopPaymentOnboarding)
        .filter(uuid_eq(ShopPaymentOnboarding.tenant_id, merchant.tenant_id))
        .first()
    )
    if po is None:
        po = ShopPaymentOnboarding(
            id=uuid.uuid4(),
            tenant_id=merchant.tenant_id,
            merchant_id=merchant.id,
        )
        db.add(po)
    po.onboarding_status = "approved"
    po.settlement_bank = "招商银行"
    po.settlement_account = "1100123456789012"
    po.settlement_account_name = merchant.legal_name or merchant.display_name
    po.wx_sub_mch_id = f"sub{str(merchant.id).replace('-', '')[:10]}"
    po.mch_name = merchant.display_name
    po.submitted_at = po.submitted_at or _now() - timedelta(days=20)
    po.approved_at = po.approved_at or _now() - timedelta(days=18)
    po.submitted_by = user.id
    cs = (
        db.query(ShopChannelSetting)
        .filter(uuid_eq(ShopChannelSetting.tenant_id, merchant.tenant_id))
        .first()
    )
    if cs is None:
        cs = ShopChannelSetting(id=uuid.uuid4(), tenant_id=merchant.tenant_id)
        db.add(cs)
    cs.enabled_combos = ["1A", "1B"]
    cs.deal_link = "1"
    cs.path_mode = "A"
    cs.bind_status = "bound"
    cs.douyin_shop_id = f"dy{spec_idx(merchant)}"
    cs.douyin_configured = True
    cs.webhook_verified = True
    db.flush()


def spec_idx(merchant: ShopMerchantAccount) -> str:
    return str(merchant.id).replace("-", "")[:8]


def _fill_claim_tokens(db, orders: list[ShopOrder]) -> None:
    for o in orders:
        if o.status != "claim_pending" or not o.claim_token:
            continue
        hit = db.query(ShopClaimToken).filter(ShopClaimToken.token == o.claim_token).first()
        if hit:
            continue
        db.add(
            ShopClaimToken(
                id=uuid.uuid4(),
                tenant_id=o.tenant_id,
                order_id=o.id,
                buyer_mobile=o.buyer_mobile_snapshot or "13700000000",
                token=o.claim_token,
                status="pending",
                expires_at=o.claim_expires_at or (_now() + timedelta(days=7)),
            )
        )
    db.flush()


def _fill_platform_categories(db) -> None:
    names = [
        "职业培训", "销售话术", "短视频运营", "直播带货", "私域获客", "社群运营",
        "IP打造", "内容创作", "投放获客", "企业服务", "咨询陪跑", "资料工具",
        "门店私域", "教育培训", "财经理财", "健康养生", "亲子教育", "考研考证",
        "设计创意", "编程开发", "办公软件", "语言学习", "管理领导力", "客户成功",
        "新媒体矩阵", "小红书运营", "视频号运营", "成交训练", "复购转介绍", "线索培育",
        "报价谈判", "门店SOP", "师资培训", "招商加盟", "渠道分销", "品牌定位",
    ]
    existing_codes = {c for (c,) in db.query(ShopPlatformCategory.code).all()}
    existing_names = {n for (n,) in db.query(ShopPlatformCategory.name).all()}
    for i, name in enumerate(names, start=1):
        code = f"vol.cat.{i:02d}"
        if code in existing_codes:
            continue
        final = name if name not in existing_names else f"{name}·演示{i:02d}"
        db.add(
            ShopPlatformCategory(
                id=uuid.uuid4(),
                parent_id=None,
                name=final,
                code=code,
                code_source="manual",
                platform_fee_bps=180 + (i % 5) * 20,
                settlement_rule="standard",
                require_qualifications=["办学许可证"] if i % 5 == 0 else [],
                status="enabled" if i <= 32 else "disabled",
                description="验收演示类目",
            )
        )
        existing_names.add(final)
    db.flush()


def _assign_categories(db) -> None:
    cats = (
        db.query(ShopPlatformCategory)
        .filter(ShopPlatformCategory.code.like("vol.cat.%"), ShopPlatformCategory.status == "enabled")
        .all()
    )
    if not cats:
        return
    products = (
        db.query(ShopProduct)
        .filter(ShopProduct.name.like(f"{VOLUME_PREFIX}%"), ShopProduct.category_id.is_(None))
        .all()
    )
    for i, p in enumerate(products):
        p.category_id = cats[i % len(cats)].id
    db.flush()


def _fill_tags(db, *, merchant, operator_id) -> None:
    names = ["高意向", "知识付费", "私域", "咨询陪跑", "资料店", "待续费", "标杆客户", "新签"]
    colors = ["blue", "green", "orange", "red", "purple", "cyan", "gold", "lime"]
    for name, color in zip(names, colors):
        tag = db.query(ShopMerchantTag).filter(ShopMerchantTag.name == f"{VOLUME_PREFIX}·{name}").first()
        if tag is None:
            tag = ShopMerchantTag(
                id=uuid.uuid4(),
                name=f"{VOLUME_PREFIX}·{name}",
                color=color,
                created_by=operator_id,
            )
            db.add(tag)
            db.flush()
        link = (
            db.query(ShopMerchantTagLink)
            .filter(
                uuid_eq(ShopMerchantTagLink.merchant_id, merchant.id),
                uuid_eq(ShopMerchantTagLink.tag_id, tag.id),
            )
            .first()
        )
        if link is None and operator_id:
            db.add(
                ShopMerchantTagLink(
                    merchant_id=merchant.id,
                    tag_id=tag.id,
                    tagged_by=operator_id,
                )
            )
            tag.usage_count = int(tag.usage_count or 0) + 1
    db.flush()


def _resolve_tenant(db, spec: dict, user: User) -> tuple:
    """复用开箱主商家时，按展示名找回「演示·经营中商家」，避免用户被测例改派到残留租户。"""
    if spec.get("reuse"):
        hit = (
            db.query(ShopMerchantAccount)
            .filter(ShopMerchantAccount.display_name == spec["display_name"])
            .first()
        )
        if hit is None:
            hit = (
                db.query(ShopMerchantAccount)
                .filter(
                    ShopMerchantAccount.contact_mobile == spec["phone"],
                    ShopMerchantAccount.status == "active",
                    ShopMerchantAccount.display_name.like("演示%"),
                )
                .first()
            )
        if hit is not None:
            db.execute(
                text("UPDATE users SET tenant_id = :tid WHERE phone = :phone"),
                {"tid": str(hit.tenant_id), "phone": spec["phone"]},
            )
            db.flush()
            db.expire(user)
            user = db.query(User).filter(User.phone == spec["phone"]).first()
            tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, hit.tenant_id)).first()
            return tenant, user
    if user.tenant_id is None:
        from app.services.membership_service import create_tenant_with_admin

        create_tenant_with_admin(
            db,
            name=spec["tenant_name"] or f"{TENANT_PREFIX}{spec['idx']:02d}",
            industry_code="education",
            user=user,
        )
        user = db.query(User).filter(User.phone == spec["phone"]).first()
    tenant = db.query(Tenant).filter(uuid_eq(Tenant.id, user.tenant_id)).first()
    return tenant, user


def _seed_one(db, spec: dict, cs_id, operator_id) -> dict:
    rng = random.Random(20260815 + spec["idx"])
    user = _ensure_user(
        db,
        phone=spec["phone"],
        password=spec["password"],
        display_name=spec["account_name"],
        tenant_name=None if spec["reuse"] else spec["tenant_name"],
    )
    tenant, user = _resolve_tenant(db, spec, user)
    merchant = _merchant(
        db,
        tenant=tenant,
        user=user,
        status="active",
        display_name=spec["display_name"],
        plan_label="基础版",
        plan_status="active",
        cs_id=cs_id,
    )
    stores = _ensure_stores(db, merchant)
    shop = stores[0]
    _ensure_payment_config(db, merchant=merchant, shop=shop, user_id=user.id)
    _plan_and_sub(db, merchant, operator_id)
    _bind_admin(db, user, tenant.id)

    products = _catalog_volume(db, merchant, shop, user, spec, rng)
    on_sale = [p for p in products if p.status == "on_sale"]
    if not on_sale:
        on_sale = products[:1]

    buyers = [
        _ensure_buyer(db, tenant_id=merchant.tenant_id, idx=spec["idx"], seq=seq)
        for seq in range(1, spec["n_buyers"] + 1)
    ]

    statuses = _order_status_plan(spec["n_orders"])
    rng.shuffle(statuses)
    orders: list[ShopOrder] = []
    now = _now()
    for i, st in enumerate(statuses, start=1):
        no = f"{ORDER_PREFIX}{spec['idx']}{i:04d}"
        product = on_sale[i % len(on_sale)]
        buyer = buyers[i % len(buyers)]
        created = now - timedelta(days=rng.randint(1, 48), hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        orders.append(
            _ensure_order(
                db,
                no=no,
                tenant_id=merchant.tenant_id,
                shop_id=shop.id,
                buyer=buyer,
                product=product,
                status=st,
                created_at=created,
                rng=rng,
            )
        )
    _ensure_invoices(db, orders, rng)
    _ensure_settlement(db, merchant=merchant, shop=shop, orders=orders, idx=spec["idx"])
    _ensure_mappings(db, products, shop)
    _fill_extra_content(db, merchant=merchant, shop=shop, user=user, spec=spec)
    _fill_bookings_and_verify(db, merchant=merchant, shop=shop, user=user, rng=rng)
    _fill_progress_and_downloads(db, merchant=merchant)
    _ensure_approved_onboarding(db, merchant=merchant, user=user)
    _fill_service_logs(db, merchant=merchant, operator_id=cs_id or operator_id, spec=spec)
    _fill_audit_logs(db, merchant=merchant, operator_id=cs_id or operator_id, spec=spec)
    _fill_sms_logs(db, merchant=merchant, shop=shop, buyers=buyers)
    _fill_moderation(db, merchant=merchant, shop=shop, products=products, orders=orders, spec=spec)
    _fill_payment_and_channel(db, merchant=merchant, shop=shop, user=user)
    _fill_claim_tokens(db, orders)
    _fill_tags(db, merchant=merchant, operator_id=cs_id or operator_id)

    n_prod = (
        db.query(ShopProduct)
        .filter(uuid_eq(ShopProduct.tenant_id, merchant.tenant_id), ShopProduct.deleted_at.is_(None))
        .count()
    )
    n_ord = db.query(ShopOrder).filter(uuid_eq(ShopOrder.tenant_id, merchant.tenant_id)).count()
    n_buy = db.query(ShopBuyer).filter(uuid_eq(ShopBuyer.tenant_id, merchant.tenant_id)).count()
    n_col = db.query(ShopColumn).filter(uuid_eq(ShopColumn.tenant_id, merchant.tenant_id)).count()
    n_pkg = db.query(ShopDigitalPackage).filter(uuid_eq(ShopDigitalPackage.tenant_id, merchant.tenant_id)).count()
    n_off = db.query(ShopServiceOffer).filter(uuid_eq(ShopServiceOffer.tenant_id, merchant.tenant_id)).count()
    n_inv = db.query(ShopInvoiceRequest).filter(uuid_eq(ShopInvoiceRequest.tenant_id, merchant.tenant_id)).count()
    n_book = db.query(ShopBooking).filter(uuid_eq(ShopBooking.tenant_id, merchant.tenant_id)).count()
    n_vf = db.query(ShopVerification).filter(uuid_eq(ShopVerification.tenant_id, merchant.tenant_id)).count()
    n_map = db.query(ShopChannelMapping).filter(uuid_eq(ShopChannelMapping.tenant_id, merchant.tenant_id)).count()
    n_ent = db.query(ShopEntitlement).filter(uuid_eq(ShopEntitlement.tenant_id, merchant.tenant_id)).count()
    return {
        "phone": spec["phone"],
        "password": spec["password"],
        "name": spec["display_name"],
        "tenant_id": str(merchant.tenant_id),
        "shop_id": str(shop.id),
        "products": n_prod,
        "orders": n_ord,
        "on_sale": sum(1 for p in products if p.status == "on_sale"),
        "buyers": n_buy,
        "columns": n_col,
        "packages": n_pkg,
        "offers": n_off,
        "invoices": n_inv,
        "bookings": n_book,
        "verifications": n_vf,
        "mappings": n_map,
        "entitlements": n_ent,
    }


def seed_full(reset_volume: bool = False) -> dict:
    min_info = seed_min(reset=False)
    db = SessionLocal()
    try:
        if reset_volume:
            _reset_volume(db)
            db.commit()
        super_user = db.query(User).filter(User.phone == ACCOUNTS["platform_super"]["phone"]).first()
        cs = db.query(User).filter(User.phone == ACCOUNTS["platform_cs"]["phone"]).first()
        summaries = []
        for spec in VOLUME_MERCHANTS:
            summaries.append(
                _seed_one(
                    db,
                    spec,
                    cs_id=cs.id if cs else None,
                    operator_id=super_user.id if super_user else None,
                )
            )
            db.flush()
        _fill_platform_categories(db)
        _assign_categories(db)
        db.commit()
        return {"min": min_info, "merchants": summaries}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def print_table(info: dict) -> None:
    print("")
    print("=== 验收演示商家（经营中 · 量级数据）===")
    for m in info["merchants"]:
        print(
            f"  {m['name']:16} {m['phone']}  {m['password']:12}  "
            f"商品 {m['products']:3}  订单 {m['orders']:3}  买家 {m.get('buyers', 0):3}  "
            f"专栏 {m.get('columns', 0):3}  资料 {m.get('packages', 0):3}  服务 {m.get('offers', 0):3}"
        )
        print(
            f"  {'':16} {'':12}  {'':12}  "
            f"发票 {m.get('invoices', 0):3}  预约 {m.get('bookings', 0):3}  核销 {m.get('verifications', 0):3}  "
            f"映射 {m.get('mappings', 0):3}  权益 {m.get('entitlements', 0):3}"
        )
    print("")
    print(f"平台超管  13800000000 / admin123456  → {web_link('/admin/login')}（商家列表可见 4 家经营中）")
    print(f"主商家    13900000099 / test123456   → {web_link('/login')} → 商城看板 / 商品 / 订单")
    print("短信验证码固定 1111。买家 H5 仍用开箱 openid=demo_buyer_paid（最小集已购链路）。")
    min_info = info["min"]
    first = info["merchants"][0]
    print(f"主商家 tenant_id = {first['tenant_id']}")
    print(
        f"旗舰店首页 = {h5_link(f'#/pages/shop/home?shop_id={first['shop_id']}&tenant_id={first['tenant_id']}&openid=demo_buyer_paid')}"
    )
    print(
        f"买家已购   = {h5_link(f'#/pages/shop/entitlements?tenant_id={min_info['tenant_id']}&openid={min_info['buyer_openid']}')}"
    )
    print(
        f"领权       = {h5_link(f'#/pages/shop/claim?token={min_info['claim_token']}&tenant_id={min_info['tenant_id']}')}"
    )
    print("")
    print("=== 另外三家店首页（翻列表用）===")
    for m in info["merchants"][1:]:
        print(
            f"  {m['name']:16} {h5_link(f'#/pages/shop/home?shop_id={m['shop_id']}&tenant_id={m['tenant_id']}&openid=demo_buyer_paid')}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="商城验收演示量级种子")
    parser.add_argument("--reset-volume", action="store_true", help="清演示量目录后重建")
    args = parser.parse_args()
    info = seed_full(reset_volume=args.reset_volume)
    print("seed_shop_demo_full: ok")
    print_table(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
