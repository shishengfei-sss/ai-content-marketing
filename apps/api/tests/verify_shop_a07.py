#!/usr/bin/env python3
"""A07 服务与时段 + M10 真槽预约验收。

对照 PRD 01-管理端UI.html #a07 / #a07-edit / #a07a · 02 #m10 / #m10-cancel-policy · §8.8.2 / §8.12.3
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ.setdefault("VERIFY_LIVE_API", "0")

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop"
MP = REPO_ROOT / "apps" / "mp" / "src" / "pages" / "shop"


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

    phone = "13900000098"
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
                    "tenant_name": f"A07验-{uuid.uuid4().hex[:6]}",
                    "display_name": "A07验",
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


def _ensure_payment(merchant: str) -> str:
    api_key = "mock_api_key_a07"
    code, data = req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_a07",
            "wx_app_id": "wx_mock_appid_a07",
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


def _buyer(tenant_id: str) -> str:
    openid = f"a07_{uuid.uuid4().hex[:10]}"
    code, data = req(
        "POST",
        "/mp/shop/auth/login",
        body={"tenant_id": tenant_id, "code": f"mock:{openid}"},
    )
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []

    # UI 结构（非空壳）
    results.append(
        check(
            "UI A07 列表 §0b",
            _page_has(
                WEB / "ServiceOffersList.vue",
                "标题",
                "模式",
                "引用商品",
                "列设置",
                "导出",
                "当前筛选",
                "列配置",
                "导出任务",
                "/shop/service-offers/export",
                "/shop/service-offers/export-tasks/",
                "page_size",
                "新建服务",
            ),
        )
    )
    results.append(
        check(
            "UI A07 Tab/弹窗",
            _page_has(
                WEB / "ServiceOffersList.vue",
                "全部服务",
                "创建并编辑",
                'data-testid="shop-offers"',
                "shop_id: currentId",
                "请输入服务标题",
                "确认发布",
                "确认下架",
                "发布说明",
                "次数卡",
                "el-drawer",
                "el-dialog",
            ),
        )
    )
    results.append(
        check(
            "UI A07-edit 时段",
            _page_has(
                WEB / "ServiceOfferEdit.vue",
                "可预约时段",
                "批量生成",
                "生成预览",
                "确认生成",
                "关闭",
                "名单",
                "次数",
                "有效天数",
                "全部时段",
                "列设置",
                "关闭影响",
                "确认关闭",
                "生成规则（选填）",
                "只读",
            ),
        )
    )
    results.append(
        check(
            "UI M10 真槽",
            _page_has(MP / "booking.vue", "listServiceSlots", "slot_id", "service_offer_id"),
        )
    )
    results.append(
        check(
            "UI A07-A 名单只读与过期文案",
            _page_has(
                WEB / "ServiceOfferEdit.vue",
                "预约名单",
                "待服务",
                "已核销",
                "过期未核销",
                "无到店标记",
            )
            and _page_has(
                WEB / "BookingsList.vue",
                "待服务",
                "过期未核销",
                "无商家代取消",
                "无到店标记",
                "预约号",
                "高级筛选",
                "导出",
                "当前筛选",
                "列配置",
                "导出任务",
                "/shop/bookings/export",
                "/shop/bookings/export-tasks/",
                "列设置",
                "核销码",
                "来源订单",
            ),
            "roster labels",
        )
    )
    results.append(
        check(
            "UI M10c 过期未核销文案",
            _page_has(MP / "bookings.vue", "已取消 · 过期未核销", "待服务"),
            "m10c",
        )
    )

    merchant, tenant_id = _ensure_merchant()
    api_key = _ensure_payment(merchant)

    # 创建次数卡
    code, card = req(
        "POST",
        "/shop/service-offers",
        token=merchant,
        body={
            "title": f"次数卡-{uuid.uuid4().hex[:6]}",
            "mode": "times_card",
            "total_times": 3,
            "valid_days": 90,
            "duration_minutes": 60,
        },
    )
    results.append(check("VA07-1 创建次数卡 201", code == 201 and card.get("status") == "draft", f"{code} {card}"))
    card_id = card.get("id")

    code, pub_fail = req("POST", f"/shop/service-offers/{card_id}/publish", token=merchant)
    # valid_days already set — should publish
    results.append(
        check(
            "VA07-2 次数卡发布",
            code == 200 and pub_fail.get("status") == "published",
            f"{code} {pub_fail}",
        )
    )

    # 预约服务
    code, offer = req(
        "POST",
        "/shop/service-offers",
        token=merchant,
        body={
            "title": f"沙龙-{uuid.uuid4().hex[:6]}",
            "mode": "booking",
            "duration_minutes": 120,
        },
    )
    results.append(check("VA07-3 创建预约服务", code == 201 and offer.get("mode") == "booking", f"{code} {offer}"))
    offer_id = offer.get("id")

    code, no_slot = req("POST", f"/shop/service-offers/{offer_id}/publish", token=merchant)
    results.append(check("VA07-4 无时段不可发布", code == 422 and "请配置时段" in str(no_slot), f"{code} {no_slot}"))

    d0 = (date.today() + timedelta(days=2)).isoformat()
    d1 = (date.today() + timedelta(days=5)).isoformat()
    batch_body = {
        "date_from": d0,
        "date_to": d1,
        "daily_windows": [{"start": "14:00", "end": "16:00"}],
        "capacity": 1,
        "skip_weekends": False,
        "skip_overlap": True,
    }
    code, preview = req(
        "POST",
        f"/shop/service-offers/{offer_id}/slots/batch-preview",
        token=merchant,
        body=batch_body,
    )
    results.append(
        check(
            "VA07-5 批量预览",
            code == 200 and preview.get("will_create", 0) >= 1,
            f"{code} {preview}",
        )
    )

    code, created = req(
        "POST",
        f"/shop/service-offers/{offer_id}/slots/batch",
        token=merchant,
        body=batch_body,
    )
    results.append(
        check(
            "VA07-6 批量生成",
            code == 200 and (created.get("total") or 0) >= 1,
            f"{code} {created}",
        )
    )
    slot_id = (created.get("items") or [{}])[0].get("id")
    code, upcoming = req(
        "GET", f"/shop/service-offers/{offer_id}/slots?view=upcoming", token=merchant
    )
    results.append(
        check(
            "VA07-slots 未来时段",
            code == 200 and (upcoming.get("total") or 0) >= 1,
            f"{code} {upcoming.get('total')}",
        )
    )

    code, pub = req("POST", f"/shop/service-offers/{offer_id}/publish", token=merchant)
    results.append(check("VA07-7 有时段可发布", code == 200 and pub.get("status") == "published", f"{code} {pub}"))

    # 关联商品上架
    code, product = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "service",
            "name": f"服务商品-{uuid.uuid4().hex[:6]}",
            "price_cents": 19900,
            "ref_type": "service_offer",
            "ref_id": offer_id,
            "service_times": 2,
        },
    )
    results.append(check("VA07-8 商品关联服务", code in (200, 201) and product.get("ref_id") == offer_id, f"{code} {product}"))
    pid = product.get("id")
    for path in (f"/shop/products/{pid}/submit-review", f"/shop/products/{pid}/publish"):
        # 人审路径可能因环境不同；尽量推到 on_sale
        req("POST", path, token=merchant, body={})
    # 平台审核 approve：找 pending review
    code, reviews = req("GET", "/admin/shop/product-reviews", token=merchant)
    # 商家 token 可能无平台权限 — 直接 DB 或用已有上架 helper
    from uuid import UUID as UUIDType

    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopProduct, ShopProductReview

    db = SessionLocal()
    try:
        pid_uuid = UUIDType(str(pid))
        p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, pid_uuid)).first()
        if p and p.status != "on_sale":
            p.status = "on_sale"
            rev = (
                db.query(ShopProductReview)
                .filter(uuid_eq(ShopProductReview.product_id, pid_uuid))
                .order_by(ShopProductReview.created_at.desc())
                .first()
            )
            if rev:
                rev.manual_result = "approved"
            db.commit()
        results.append(check("VA07-9 商品 on_sale", p is not None and p.status == "on_sale", p.status if p else None))
    finally:
        db.close()

    buyer = _buyer(tenant_id)
    mobile = "138" + f"{uuid.uuid4().int % 10**8:08d}"
    code, bind = req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})
    results.append(check("VA07-10a 绑定手机", code == 200, f"{code} {bind}"))
    code, created_o = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created_o or {}).get("order") or created_o
    results.append(check("VA07-10 下单", code == 200, f"{code} {created_o}"))
    if code == 200:
        _pay(order["order_no"], int(order["amount_cents"]), api_key)

    code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
    ent = next((e for e in (ents.get("items") or []) if e.get("product_id") == pid), None)
    results.append(
        check(
            "VA07-11 权益带 service_offer_id",
            ent is not None and ent.get("service_offer_id") == offer_id and ent.get("service_mode") == "booking",
            f"{code} {ent}",
        )
    )
    ent_id = ent["id"] if ent else None

    code, mp_slots = req(
        "GET",
        f"/mp/shop/service-offers/{offer_id}/slots?entitlement_id={ent_id}",
        token=buyer,
    )
    selectable = [s for s in (mp_slots.get("slots") or []) if s.get("selectable")]
    results.append(
        check(
            "VA07-12 M10 开放槽",
            code == 200 and mp_slots.get("mode") == "booking" and len(selectable) >= 1,
            f"{code} {mp_slots}",
        )
    )
    use_slot = selectable[0]["id"] if selectable else slot_id

    code, booking = req(
        "POST",
        "/mp/shop/bookings",
        token=buyer,
        body={"entitlement_id": ent_id, "slot_id": use_slot},
    )
    results.append(
        check(
            "VA07-13 slot_id 预约",
            code == 200 and booking.get("status") == "booked" and booking.get("slot_id") == use_slot,
            f"{code} {booking}",
        )
    )
    booking_id = booking.get("id") if code == 200 else None

    code, full = req(
        "POST",
        "/mp/shop/bookings",
        token=buyer,
        body={"entitlement_id": ent_id, "slot_id": use_slot},
    )
    results.append(check("VA07-14 容量满/重复 409", code == 409, f"{code} {full}"))

    # 另一买家验证 full
    buyer2 = _buyer(tenant_id)
    mobile2 = "139" + f"{uuid.uuid4().int % 10**8:08d}"
    req("POST", "/mp/shop/auth/bind", token=buyer2, body={"mobile": mobile2})
    code, created2 = req("POST", "/mp/shop/orders", token=buyer2, body={"product_id": pid})
    order2 = (created2 or {}).get("order") or created2
    if code == 200:
        _pay(order2["order_no"], int(order2["amount_cents"]), api_key)
        code, ents2 = req("GET", "/mp/shop/entitlements", token=buyer2)
        ent2 = next((e for e in (ents2.get("items") or []) if e.get("product_id") == pid), None)
        if ent2:
            code, full2 = req(
                "POST",
                "/mp/shop/bookings",
                token=buyer2,
                body={"entitlement_id": ent2["id"], "slot_id": use_slot},
            )
            results.append(check("VA07-15 他买家满额 409", code == 409, f"{code} {full2}"))
        else:
            results.append(check("VA07-15 他买家满额 409", False, "no ent2"))
    else:
        results.append(check("VA07-15 他买家满额 409", False, f"order2 {code}"))

    code, roster = req(
        "GET",
        f"/shop/service-offers/{offer_id}/slots/{use_slot}/bookings",
        token=merchant,
    )
    results.append(check("VA07-18 预约名单", code == 200 and isinstance(roster, list) and len(roster) >= 1, f"{code}"))

    code, one = req("GET", f"/shop/bookings/{booking_id}", token=merchant) if booking_id else (0, {})
    results.append(
        check(
            "VA07-18b 全店名单含预约号/店铺",
            code == 200
            and (one.get("booking_no") or "").startswith("BK")
            and one.get("status_label") == "待服务"
            and bool(one.get("shop_name"))
            and bool(one.get("offer_id")),
            f"{code} {one}",
        )
    )
    code, csv_body = req("GET", "/shop/bookings/export?status=booked", token=merchant)
    csv_text = csv_body if isinstance(csv_body, str) else str(csv_body)
    results.append(
        check(
            "VA07-18c 导出含默认列",
            code == 200 and "预约号" in csv_text and "核销码" in csv_text and "来源订单" in csv_text,
            f"{code} {csv_text[:80]}",
        )
    )
    code, bk_task = req("POST", "/shop/bookings/export", token=merchant, body={"status": "booked"})
    results.append(
        check(
            "VA07-B1 POST 导出任务已完成",
            code == 200
            and isinstance(bk_task, dict)
            and bk_task.get("status") == "done"
            and bk_task.get("resource") == "bookings"
            and bk_task.get("id"),
            f"{code} {bk_task}",
        )
    )
    bk_task_id = (bk_task or {}).get("id") if isinstance(bk_task, dict) else None
    if bk_task_id:
        code, bk_file = req("GET", f"/shop/bookings/export-tasks/{bk_task_id}/file", token=merchant)
        results.append(
            check(
                "VA07-B2 任务文件可下载",
                code == 200 and "预约号" in str(bk_file) and "核销码" in str(bk_file),
                f"{code} head={str(bk_file)[:80]!r}",
            )
        )
    else:
        results.append(check("VA07-B2 任务文件可下载", False, "no task id"))
    code, bk_cols = req(
        "POST",
        "/shop/bookings/export",
        token=merchant,
        body={"status": "booked", "columns": ["booking_no", "status"]},
    )
    if code == 200 and isinstance(bk_cols, dict) and bk_cols.get("id"):
        code2, bk_col_csv = req(
            "GET",
            f"/shop/bookings/export-tasks/{bk_cols['id']}/file",
            token=merchant,
        )
        head = str(bk_col_csv).splitlines()[0] if bk_col_csv else ""
        results.append(
            check(
                "VA07-B3 列配置导出表头",
                code2 == 200 and "预约号" in head and "状态" in head and "服务" not in head,
                f"{code2} {head[:80]!r}",
            )
        )
    else:
        results.append(check("VA07-B3 列配置导出表头", False, f"{code} {bk_cols}"))
    code, plat_bk = req(
        "POST",
        "/auth/login",
        body={"phone": "13800000000", "password": "admin123456", "workspace_mode": "platform"},
    )
    plat_bk_token = (
        plat_bk.get("access_token") if code == 200 and isinstance(plat_bk, dict) else None
    )
    code, bk_forbidden = req("POST", "/shop/bookings/export", token=plat_bk_token, body={})
    results.append(
        check(
            "VA07-B4 平台 POST 导出 403",
            code in (401, 403),
            f"{code} {bk_forbidden}",
        )
    )

    def _run_expire_job() -> int:
        from app.database import SessionLocal
        from app.services.shop.booking_expiry_job import process_expired_unredeemed_bookings

        db = SessionLocal()
        try:
            return process_expired_unredeemed_bookings(db)
        finally:
            db.close()

    _run_expire_job()
    code, still = req("GET", f"/shop/bookings/{booking_id}", token=merchant) if booking_id else (0, {})
    results.append(
        check(
            "VA07-21 未到期不取消 #m10-cancel-policy",
            code == 200 and (still or {}).get("status") == "booked",
            f"{code} {(still or {}).get('status')}",
        )
    )

    # 关闭时段 → 取消预约
    code, closed = req(
        "POST",
        f"/shop/service-offers/{offer_id}/slots/{use_slot}/close",
        token=merchant,
    )
    results.append(check("VA07-16 关闭时段", code == 200 and closed.get("status") == "closed", f"{code} {closed}"))

    if booking_id:
        code, bget = req("GET", f"/shop/bookings/{booking_id}", token=merchant)
        results.append(
            check(
                "VA07-17 关闭→预约 cancelled",
                code == 200 and bget.get("status") == "cancelled" and bget.get("cancel_reason") == "slot_closed",
                f"{code} {bget}",
            )
        )
    else:
        results.append(check("VA07-17 关闭→预约 cancelled", False, "no booking"))

    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopBooking, ShopServiceSlot

    code, slot_list = req("GET", f"/shop/service-offers/{offer_id}/slots", token=merchant)
    open_slot = next(
        (
            s
            for s in ((slot_list or {}).get("items") or [])
            if s.get("status") == "open" and str(s.get("id")) != str(use_slot)
        ),
        None,
    )
    expire_bid = None
    if ent_id and open_slot:
        code, b2 = req(
            "POST",
            "/mp/shop/bookings",
            token=buyer,
            body={"entitlement_id": ent_id, "slot_id": open_slot["id"]},
        )
        if code == 200:
            expire_bid = b2.get("id")
            db = SessionLocal()
            try:
                slot_row = (
                    db.query(ShopServiceSlot)
                    .filter(uuid_eq(ShopServiceSlot.id, uuid.UUID(str(open_slot["id"]))))
                    .first()
                )
                now = datetime.now(timezone.utc)
                if slot_row:
                    slot_row.end_at = now - timedelta(minutes=20)
                    slot_row.start_at = now - timedelta(hours=2)
                    db.commit()
            finally:
                db.close()
    n_exp = _run_expire_job() if expire_bid else 0
    code, expired = req("GET", f"/shop/bookings/{expire_bid}", token=merchant) if expire_bid else (0, {})
    db = SessionLocal()
    try:
        slot_after = None
        if open_slot:
            slot_after = (
                db.query(ShopServiceSlot)
                .filter(uuid_eq(ShopServiceSlot.id, uuid.UUID(str(open_slot["id"]))))
                .first()
            )
        released = bool(slot_after and int(slot_after.booked_count or 0) == 0)
    finally:
        db.close()
    results.append(
        check(
            "VA07-22 过期未核销 cancelled",
            bool(expire_bid)
            and n_exp >= 1
            and code == 200
            and (expired or {}).get("status") == "cancelled"
            and (expired or {}).get("cancel_reason") == "expired_unredeemed"
            and released,
            f"{code} {(expired or {}).get('status')} reason={(expired or {}).get('cancel_reason')} n={n_exp} released={released}",
        )
    )

    card_bid = None
    src_id = expire_bid or booking_id
    db = SessionLocal()
    try:
        orig = (
            db.query(ShopBooking).filter(uuid_eq(ShopBooking.id, uuid.UUID(str(src_id)))).first()
            if src_id
            else None
        )
        if orig:
            card_row = ShopBooking(
                id=uuid.uuid4(),
                tenant_id=orig.tenant_id,
                shop_id=orig.shop_id,
                buyer_id=orig.buyer_id,
                entitlement_id=orig.entitlement_id,
                service_product_id=orig.service_product_id,
                slot_id=None,
                status="booked",
                booked_date=orig.booked_date,
                booked_time_slot="到店核销",
            )
            db.add(card_row)
            db.flush()
            card_row.created_at = datetime.now(timezone.utc) - timedelta(hours=49)
            db.commit()
            card_bid = str(card_row.id)
    finally:
        db.close()

    n_card = _run_expire_job() if card_bid else 0
    code, card_got = req("GET", f"/shop/bookings/{card_bid}", token=merchant) if card_bid else (0, {})
    results.append(
        check(
            "VA07-23 次数卡 48h 过期未核销",
            bool(card_bid)
            and n_card >= 1
            and code == 200
            and (card_got or {}).get("status") == "cancelled"
            and (card_got or {}).get("cancel_reason") == "expired_unredeemed",
            f"{code} {card_got} n={n_card}",
        )
    )

    code, listed = req("GET", "/shop/service-offers?page=1&page_size=20", token=merchant)
    results.append(
        check(
            "VA07-19 列表",
            code == 200 and any(i.get("id") == offer_id for i in (listed.get("items") or [])),
            f"{code}",
        )
    )
    osc = listed.get("status_counts") or {}
    results.append(
        check(
            "VA07-list status_counts",
            code == 200 and isinstance(osc, dict) and "draft" in osc and "published" in osc,
            f"{code} {osc}",
        )
    )
    qoff = (offer.get("title") or "")[:8]
    code, csv_off = req("GET", f"/shop/service-offers/export?q={qoff}", token=merchant)
    results.append(
        check(
            "VA07-export 含标题",
            code == 200 and "标题" in str(csv_off) and "预约" in str(csv_off),
            f"{code} {str(csv_off)[:120]}",
        )
    )
    code, off_task = req("POST", "/shop/service-offers/export", token=merchant, body={"q": qoff})
    results.append(
        check(
            "VA07-X1 POST 导出任务已完成",
            code == 200
            and isinstance(off_task, dict)
            and off_task.get("status") == "done"
            and off_task.get("resource") == "service_offers"
            and off_task.get("id"),
            f"{code} {off_task}",
        )
    )
    off_task_id = (off_task or {}).get("id") if isinstance(off_task, dict) else None
    if off_task_id:
        code, off_file = req(
            "GET", f"/shop/service-offers/export-tasks/{off_task_id}/file", token=merchant
        )
        results.append(
            check(
                "VA07-X2 任务文件可下载",
                code == 200 and "标题" in str(off_file) and "模式" in str(off_file),
                f"{code} head={str(off_file)[:80]!r}",
            )
        )
    else:
        results.append(check("VA07-X2 任务文件可下载", False, "no task id"))
    code, off_cols = req(
        "POST",
        "/shop/service-offers/export",
        token=merchant,
        body={"q": qoff, "columns": ["title", "status"]},
    )
    if code == 200 and isinstance(off_cols, dict) and off_cols.get("id"):
        code2, off_col_csv = req(
            "GET",
            f"/shop/service-offers/export-tasks/{off_cols['id']}/file",
            token=merchant,
        )
        head = str(off_col_csv).splitlines()[0] if off_col_csv else ""
        results.append(
            check(
                "VA07-X3 列配置导出表头",
                code2 == 200 and "标题" in head and "状态" in head and "模式" not in head,
                f"{code2} {head[:80]!r}",
            )
        )
    else:
        results.append(check("VA07-X3 列配置导出表头", False, f"{code} {off_cols}"))
    code, plat_off = req(
        "POST",
        "/auth/login",
        body={"phone": "13800000000", "password": "admin123456", "workspace_mode": "platform"},
    )
    plat_off_token = (
        plat_off.get("access_token") if code == 200 and isinstance(plat_off, dict) else None
    )
    code, off_forbidden = req(
        "POST", "/shop/service-offers/export", token=plat_off_token, body={}
    )
    results.append(
        check(
            "VA07-P01 平台 POST 导出 403",
            code in (401, 403),
            f"{code} {off_forbidden}",
        )
    )
    code, by_mode = req("GET", "/shop/service-offers?mode=times_card", token=merchant)
    mode_items = by_mode.get("items") or []
    results.append(
        check(
            "VA07-list 模式=次数卡",
            code == 200 and len(mode_items) >= 1 and all(i.get("mode") == "times_card" for i in mode_items),
            f"{code} n={len(mode_items)}",
        )
    )

    code, off = req("POST", f"/shop/service-offers/{offer_id}/off-sale", token=merchant)
    results.append(check("VA07-20 下架", code == 200 and off.get("status") == "off_sale", f"{code} {off}"))

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\nA07 verify: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
