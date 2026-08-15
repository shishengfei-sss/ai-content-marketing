#!/usr/bin/env python3
"""A11 买家 / A12 权益验收。对照 PRD #a11 / #a11a / #a12 / #a12a。"""

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

    phone = "13900000094"
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
                    "tenant_name": f"A11验-{uuid.uuid4().hex[:6]}",
                    "display_name": "A11验",
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


def main() -> int:
    results: list[bool] = []
    buyers_src = (WEB / "BuyersList.vue").read_text(encoding="utf-8")
    results.append(
        check(
            "UI A11 列表",
            _page_has(
                WEB / "BuyersList.vue",
                "手机",
                "昵称",
                "账号状态",
                "来源店铺",
                "订单数",
                "权益数",
                "累计消费",
                "注册渠道",
                "最近下单",
                "注册时间",
                "导出",
                "列设置",
                "高级筛选",
                "全部买家",
                "有权益",
                "近 7 日新注册",
                "已封禁",
                "首单时间",
                "buyer_id（技术）",
                "手机 / 昵称",
                "订单数 ≥",
                "权益数 ≥",
                "注册起",
                "最近下单起",
                "data-testid=\"shop-buyers\"",
            ),
        )
    )
    results.append(
        check(
            "UI A11 禁止同步 CRM",
            "同步到 CRM" not in buyers_src and "升级为客户" not in buyers_src,
        )
    )
    results.append(
        check(
            "UI A11 导出下拉与任务弹窗",
            "当前筛选" in buyers_src
            and "选中行" in buyers_src
            and "导出任务" in buyers_src
            and "export-tasks" in buyers_src
            and "/shop/buyers/export" in buyers_src
            and "ElMessageBox" not in buyers_src
            and "type=\"selection\"" in buyers_src,
            "export task dialog",
        )
    )
    results.append(
        check(
            "UI A11-A 五 Tab",
            _page_has(
                WEB / "BuyerDetail.vue",
                "订单",
                "权益",
                "预约",
                "开票",
                "学习进度",
                "reveal-sensitive",
                "预约号",
                "核销码",
                "来源订单",
                "店铺",
                "开通时间",
                "到期",
                "申请单",
                "税号",
                "专栏",
                "最近课时",
                "来源店铺",
                "data-testid=\"shop-buyer-detail\"",
            ),
        )
    )
    results.append(
        check(
            "UI A12 列表/抽屉",
            _page_has(
                WEB / "EntitlementsList.vue",
                "买家",
                "商品",
                "开通时间",
                "到期时间",
                "权益详情",
                "已用尽",
                "全部权益",
                "高级筛选",
                "列设置",
                "导出",
                "开通起",
                "到期起",
                "手机 / 订单号",
                "data-testid=\"shop-entitlements\"",
            ),
        )
    )
    entitlements_src = (WEB / "EntitlementsList.vue").read_text(encoding="utf-8")
    results.append(
        check(
            "UI A12 导出下拉与任务弹窗",
            "当前筛选" in entitlements_src
            and "导出任务" in entitlements_src
            and "export-tasks" in entitlements_src
            and "/shop/entitlements/export" in entitlements_src
            and "ElMessageBox" not in entitlements_src,
            "export task dialog",
        )
    )

    merchant, tenant_id = _ensure_merchant()
    api_key = "mock_api_key_a11"
    req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_a11",
            "wx_app_id": "wx_mock_appid_a11",
            "wx_api_key": api_key,
            "wx_notify_url": "http://127.0.0.1:8003/api/v1/mp/shop/payments/notify",
        },
    )

    # 建在售课 + 下单支付，确保列表有数据
    from tests.http_client import _get_test_client

    client = _get_test_client()
    code, col = req(
        "POST", "/shop/columns", token=merchant, body={"title": f"A11专栏-{uuid.uuid4().hex[:6]}"}
    )
    up = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {merchant}"},
        files={"file": ("a11.mp4", b"v", "video/mp4")},
    ).json()
    code, les = req(
        "POST",
        f"/shop/columns/{col['id']}/lessons",
        token=merchant,
        body={
            "title": "A11课",
            "media_type": "video",
            "media_id": up["file_id"],
            "media_url": up["file_url"],
            "duration_sec": 30,
        },
    )
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
            "name": f"A11课-{uuid.uuid4().hex[:6]}",
            "price_cents": 9900,
            "cover_url": cover,
            "ref_type": "column",
            "ref_id": col["id"],
        },
    )
    from uuid import UUID as UUIDType

    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopProduct

    db = SessionLocal()
    try:
        p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, UUIDType(product["id"]))).first()
        p.status = "on_sale"
        db.commit()
    finally:
        db.close()

    openid = f"a11_{uuid.uuid4().hex[:10]}"
    code, bl = req(
        "POST", "/mp/shop/auth/login", body={"tenant_id": tenant_id, "code": f"mock:{openid}"}
    )
    buyer_tok = bl["access_token"]
    mobile = "139" + f"{uuid.uuid4().int % 10**8:08d}"
    req("POST", "/mp/shop/auth/bind", token=buyer_tok, body={"mobile": mobile})
    code, created = req(
        "POST", "/mp/shop/orders", token=buyer_tok, body={"product_id": product["id"]}
    )
    order = (created or {}).get("order") or created
    from app.services.shop.wechat_pay_service import stub_sign

    tx = f"TX{uuid.uuid4().hex[:16]}"
    sign = stub_sign(order["order_no"], tx, int(order["amount_cents"]), api_key)
    req(
        "POST",
        "/mp/shop/payments/notify",
        body={
            "order_no": order["order_no"],
            "transaction_id": tx,
            "paid_amount_cents": int(order["amount_cents"]),
            "sign": sign,
        },
    )

    code, buyers = req("GET", "/shop/buyers", token=merchant)
    hit = next(
        (b for b in (buyers.get("items") or []) if b.get("mobile_masked") and mobile[-4:] in (b.get("mobile_masked") or "")),
        None,
    )
    results.append(
        check(
            "VA11-1 买家列表含脱敏",
            code == 200 and hit is not None and hit.get("order_count", 0) >= 1 and "****" in (hit.get("mobile_masked") or ""),
            f"{code} {hit}",
        )
    )
    buyer_id = hit["id"] if hit else None

    code, detail = req("GET", f"/shop/buyers/{buyer_id}", token=merchant) if buyer_id else (0, {})
    results.append(
        check(
            "VA11-2 买家详情",
            code == 200 and detail.get("entitlement_count", 0) >= 1,
            f"{code} {detail}",
        )
    )

    code, rev = req("POST", f"/shop/buyers/{buyer_id}/reveal-sensitive", token=merchant) if buyer_id else (0, {})
    results.append(
        check("VA11-3 揭密", code == 200 and rev.get("mobile") == mobile, f"{code} {rev}")
    )

    code, ords = req("GET", f"/shop/orders?buyer_id={buyer_id}", token=merchant) if buyer_id else (0, {})
    results.append(
        check(
            "VA11-4 按买家筛订单",
            code == 200 and any(o.get("id") == order["id"] for o in (ords.get("items") or [])),
            f"{code} {ords.get('total')}",
        )
    )

    code, ents = req("GET", "/shop/entitlements", token=merchant)
    results.append(
        check(
            "VA12-1 权益列表 enrich",
            code == 200
            and (ents.get("items") or [])
            and (ents["items"][0].get("buyer_mobile_masked") or ents["items"][0].get("order_no")),
            f"{code} {(ents.get('items') or [{}])[0]}",
        )
    )
    eid = (ents.get("items") or [{}])[0].get("id")
    code, ed = req("GET", f"/shop/entitlements/{eid}", token=merchant) if eid else (0, {})
    results.append(
        check(
            "VA12-2 权益详情",
            code == 200 and ed.get("id") == eid and "expires_at" in ed,
            f"{code} {ed}",
        )
    )
    code, future_ent = req("GET", "/shop/entitlements?activated_from=2099-01-01", token=merchant)
    results.append(
        check(
            "VA12-3 开通起未来日为空",
            code == 200 and future_ent.get("total") == 0,
            f"{code} {future_ent.get('total')}",
        )
    )
    code, csv_ent = req("GET", "/shop/entitlements/export", token=merchant)
    csv_ent_text = csv_ent if isinstance(csv_ent, str) else str(csv_ent)
    results.append(
        check(
            "VA12-4 导出含默认列头",
            code == 200 and "买家" in csv_ent_text and "开通时间" in csv_ent_text,
            f"{code} {csv_ent_text[:80]}",
        )
    )
    code, ent_task = req("POST", "/shop/entitlements/export", token=merchant, body={})
    results.append(
        check(
            "VA12-4b POST 导出任务已完成",
            code == 200
            and isinstance(ent_task, dict)
            and ent_task.get("status") == "done"
            and ent_task.get("resource") == "entitlements"
            and ent_task.get("id"),
            f"{code} {ent_task}",
        )
    )
    ent_task_id = (ent_task or {}).get("id") if isinstance(ent_task, dict) else None
    if ent_task_id:
        code, ent_file = req("GET", f"/shop/entitlements/export-tasks/{ent_task_id}/file", token=merchant)
        results.append(
            check(
                "VA12-4c 任务文件可下载",
                code == 200 and "买家" in str(ent_file) and "开通时间" in str(ent_file),
                f"{code}",
            )
        )
    else:
        results.append(check("VA12-4c 任务文件可下载", False, "no task"))
    code, active_ents = req("GET", "/shop/entitlements?status=active", token=merchant)
    consumed_in_active = [
        x
        for x in (active_ents.get("items") or [])
        if x.get("remaining_count") == 0
    ]
    results.append(
        check(
            "VA12-5 生效中不含已用尽",
            code == 200 and not consumed_in_active,
            f"{code} {len(consumed_in_active)}",
        )
    )

    code, learn = req("GET", f"/shop/buyers/{buyer_id}/learning-progress", token=merchant) if buyer_id else (0, {})
    results.append(check("VA11-5 学习进度接口", code == 200 and "items" in learn, f"{code} {learn}"))

    code, my_ents = req("GET", f"/shop/entitlements?buyer_id={buyer_id}", token=merchant) if buyer_id else (0, {})
    my_eid = next(
        (x.get("id") for x in (my_ents.get("items") or []) if x.get("order_id") == order["id"]),
        (my_ents.get("items") or [{}])[0].get("id"),
    )
    code, prog = req(
        "PUT",
        f"/mp/shop/entitlements/{my_eid}/lessons/{les['id']}/progress",
        token=buyer_tok,
        body={"course_id": col["id"], "position_sec": 8, "progress_pct": 40},
    ) if my_eid else (0, {})
    results.append(check("VA11-5b 写入学课进度", code == 200, f"{code} {prog}"))
    code, learn2 = req("GET", f"/shop/buyers/{buyer_id}/learning-progress", token=merchant) if buyer_id else (0, {})
    hit_learn = next((x for x in (learn2.get("items") or []) if x.get("entitlement_id") == my_eid), None)
    results.append(
        check(
            "VA11-13 最近课时为课时标题",
            bool(hit_learn) and hit_learn.get("last_lesson_title") == "A11课" and bool(hit_learn.get("shop_name")),
            f"{hit_learn}",
        )
    )

    code, ords2 = req("GET", f"/shop/orders?buyer_id={buyer_id}", token=merchant) if buyer_id else (0, {})
    o0 = next((x for x in (ords2.get("items") or []) if x.get("id") == order["id"]), (ords2.get("items") or [{}])[0])
    results.append(
        check(
            "VA11-14 订单行含店铺",
            code == 200 and bool(o0.get("shop_name")),
            f"{code} {o0}",
        )
    )
    e0 = next((x for x in (my_ents.get("items") or []) if x.get("id") == my_eid), (my_ents.get("items") or [{}])[0])
    results.append(
        check(
            "VA11-15 权益行含店铺",
            bool(e0.get("shop_name")) and "expires_at" in e0,
            f"{e0}",
        )
    )

    code, inv = req(
        "POST",
        "/mp/shop/invoices",
        token=buyer_tok,
        body={"order_id": order["id"], "title_type": "person", "title": "验收个人", "email": "a11@example.com"},
    )
    results.append(check("VA11-16 买家提交开票", code in (200, 201), f"{code} {inv}"))
    code, invs = req("GET", f"/shop/invoices?buyer_id={buyer_id}", token=merchant) if buyer_id else (0, {})
    i0 = next((x for x in (invs.get("items") or []) if x.get("id") == inv.get("id")), (invs.get("items") or [{}])[0])
    results.append(
        check(
            "VA11-17 开票行含申请单税号类型",
            code == 200
            and bool(i0.get("application_no"))
            and str(i0.get("application_no", "")).startswith("INV")
            and i0.get("title_type") == "person"
            and "tax_no" in i0,
            f"{code} {i0}",
        )
    )
    if i0.get("id"):
        code, one = req("GET", f"/shop/invoices/{i0['id']}", token=merchant)
        results.append(
            check(
                "VA11-18 开票详情",
                code == 200 and one.get("id") == i0["id"] and one.get("application_no"),
                f"{code} {one}",
            )
        )
    else:
        results.append(check("VA11-18 开票详情", False, "no invoice"))

    results.append(
        check(
            "VA11-6 列表含首单时间",
            bool(hit) and bool(hit.get("first_order_at")),
            f"{hit}",
        )
    )
    code, blocked = req("GET", "/shop/buyers?account_status=blocked", token=merchant)
    results.append(
        check(
            "VA11-7 账号状态已封禁恒空",
            code == 200 and blocked.get("total") == 0,
            f"{code} {blocked.get('total')}",
        )
    )
    code, tab_blocked = req("GET", "/shop/buyers?tab=blocked", token=merchant)
    results.append(
        check(
            "VA11-8 Tab 已封禁恒空",
            code == 200 and tab_blocked.get("total") == 0,
            f"{code} {tab_blocked.get('total')}",
        )
    )
    code, min_orders = req("GET", "/shop/buyers?order_count_min=1", token=merchant)
    min_hit = next(
        (b for b in (min_orders.get("items") or []) if b.get("id") == buyer_id),
        None,
    )
    results.append(
        check(
            "VA11-9 订单数≥1 含刚下单买家",
            code == 200 and min_hit is not None,
            f"{code} total={min_orders.get('total')}",
        )
    )
    code, future = req("GET", "/shop/buyers?registered_from=2099-01-01", token=merchant)
    results.append(
        check(
            "VA11-10 注册起未来日为空",
            code == 200 and future.get("total") == 0,
            f"{code} {future.get('total')}",
        )
    )
    code, csv_body = req("GET", "/shop/buyers/export", token=merchant)
    csv_text = csv_body if isinstance(csv_body, str) else str(csv_body)
    results.append(
        check(
            "VA11-11 导出含默认列头",
            code == 200 and "手机" in csv_text and "账号状态" in csv_text,
            f"{code} {csv_text[:80]}",
        )
    )
    code, csv_blocked = req("GET", "/shop/buyers/export?account_status=blocked", token=merchant)
    csv_blocked_text = csv_blocked if isinstance(csv_blocked, str) else str(csv_blocked)
    results.append(
        check(
            "VA11-12 导出跟随筛选",
            code == 200 and "手机" in csv_blocked_text and csv_blocked_text.count("\n") <= 1,
            f"{code} lines={csv_blocked_text.count(chr(10))}",
        )
    )
    code, task = req("POST", "/shop/buyers/export", token=merchant, body={})
    results.append(
        check(
            "VA11-11b POST 导出任务已完成",
            code == 200
            and isinstance(task, dict)
            and task.get("status") == "done"
            and task.get("resource") == "buyers"
            and task.get("id"),
            f"{code} {task}",
        )
    )
    task_id = (task or {}).get("id") if isinstance(task, dict) else None
    if task_id:
        code, file_csv = req("GET", f"/shop/buyers/export-tasks/{task_id}/file", token=merchant)
        results.append(
            check(
                "VA11-11c 任务文件可下载",
                code == 200 and "手机" in str(file_csv) and "账号状态" in str(file_csv),
                f"{code}",
            )
        )
    else:
        results.append(check("VA11-11c 任务文件可下载", False, "no task"))
    code, empty_sel = req("POST", "/shop/buyers/export", token=merchant, body={"buyer_ids": []})
    results.append(
        check(
            "VA11-11d 选中行空列表 422",
            code == 422 and "请先选择" in str(empty_sel),
            f"{code} {empty_sel}",
        )
    )
    if buyer_id:
        code, sel_task = req(
            "POST", "/shop/buyers/export", token=merchant, body={"buyer_ids": [buyer_id]}
        )
        sel_id = (sel_task or {}).get("id") if isinstance(sel_task, dict) else None
        if sel_id:
            code, sel_csv = req("GET", f"/shop/buyers/export-tasks/{sel_id}/file", token=merchant)
            results.append(
                check(
                    "VA11-11e 选中行仅一条",
                    code == 200
                    and "手机" in str(sel_csv)
                    and str(sel_csv).count("\n") == 1
                    and int((sel_task or {}).get("row_count") or 0) == 1,
                    f"{code} rows={str(sel_csv).count(chr(10))} task={sel_task}",
                )
            )
        else:
            results.append(check("VA11-11e 选中行仅一条", False, f"{code} {sel_task}"))
    else:
        results.append(check("VA11-11e 选中行仅一条", False, "no buyer"))

    passed = sum(1 for x in results if x)
    total = len(results)
    print(f"\nA11/A12: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
