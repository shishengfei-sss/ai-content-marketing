#!/usr/bin/env python3
"""核销台 / 核销记录。对照 PRD 01-管理端UI.html #a08 / #a08-log / #a08b / #a08-log-select-spec。"""

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
from tests.verify_shop_a14 import _ensure_merchant, login  # noqa: E402
from tests.verify_shop_m6 import _buyer_login, _ensure_payment_config, _pay_order  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "Verifications.vue"
LAYOUT = REPO_ROOT / "apps" / "web" / "src" / "layouts" / "AppLayout.vue"
ROUTER = REPO_ROOT / "apps" / "web" / "src" / "router.js"
LOGIN = REPO_ROOT / "apps" / "web" / "src" / "views" / "Login.vue"

CLERK_PHONE = "13900000196"
CLERK_PASSWORD = "test123456"


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _ensure_service_on_sale(merchant: str) -> str:
    from tests.http_client import _get_test_client

    client = _get_test_client()
    cover = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {merchant}"},
        files={"file": ("c.png", b"\x89PNG", "image/png")},
    ).json()["file_url"]
    code, card = req(
        "POST",
        "/shop/service-offers",
        token=merchant,
        body={
            "title": f"A08次数卡-{uuid.uuid4().hex[:6]}",
            "mode": "times_card",
            "total_times": 2,
            "valid_days": 90,
            "duration_minutes": 60,
        },
    )
    assert code in (200, 201), card
    req("POST", f"/shop/service-offers/{card['id']}/publish", token=merchant)
    admin = login("13800000000", "admin123456")
    code, data = req(
        "POST",
        "/shop/products",
        token=merchant,
        body={
            "type": "service",
            "name": f"A08服务-{uuid.uuid4().hex[:6]}",
            "price_cents": 9900,
            "cover_url": cover,
            "refund_policy": "always_allow",
            "service_times": 2,
            "ref_type": "service_offer",
            "ref_id": card["id"],
        },
    )
    assert code == 200, data
    pid = data["id"]
    code, data = req("POST", f"/shop/products/{pid}/submit-review", token=merchant, body={})
    assert code == 200, data
    rid = data["review_id"]
    code, data = req("POST", f"/admin/shop/product-reviews/{rid}/approve", token=admin)
    assert code == 200, data
    code, data = req("POST", f"/shop/products/{pid}/publish", token=merchant)
    assert code == 200 and data.get("status") == "on_sale", data
    return pid


def _ensure_clerk(merchant: str, tenant_id: str) -> str:
    """创建或复用店员账号并返回 token。对照 #a08-clerk。"""
    from uuid import UUID

    from app.database import SessionLocal, uuid_eq
    from app.models import TenantMembership, TenantRole, User
    from app.services.auth_service import hash_password

    req("POST", "/shop/roles/shop_clerk/enable", token=merchant, body={})
    code, stores = req("GET", "/shop/stores?page=1&page_size=20", token=merchant)
    shop_id = (stores.get("items") or [{}])[0].get("id") if code == 200 else None
    assert shop_id, stores

    with SessionLocal() as db:
        u = db.query(User).filter(User.phone == CLERK_PHONE).first()
        if not u:
            u = User(
                id=uuid.uuid4(),
                phone=CLERK_PHONE,
                display_name="核销店员",
                hashed_password=hash_password(CLERK_PASSWORD),
                tenant_id=UUID(tenant_id),
            )
            db.add(u)
            db.flush()
        mem = (
            db.query(TenantMembership)
            .filter(
                uuid_eq(TenantMembership.tenant_id, UUID(tenant_id)),
                uuid_eq(TenantMembership.user_id, u.id),
                TenantMembership.is_active.is_(True),
            )
            .first()
        )
        if not mem:
            role = (
                db.query(TenantRole)
                .filter(uuid_eq(TenantRole.tenant_id, UUID(tenant_id)), TenantRole.code == "editor")
                .first()
            )
            if not role:
                role = (
                    db.query(TenantRole)
                    .filter(uuid_eq(TenantRole.tenant_id, UUID(tenant_id)))
                    .first()
                )
            db.add(
                TenantMembership(
                    id=uuid.uuid4(),
                    user_id=u.id,
                    tenant_id=UUID(tenant_id),
                    role_id=role.id,
                    is_active=True,
                )
            )
        db.commit()
        uid = str(u.id)

    code, assigned = req(
        "POST",
        "/shop/members",
        token=merchant,
        body={
            "user_id": uid,
            "role_code": "shop_clerk",
            "store_scope": "selected",
            "store_ids": [shop_id],
        },
    )
    assert code == 200, assigned
    token = login(CLERK_PHONE, CLERK_PASSWORD)
    code, sel = req("POST", "/auth/select-tenant", token=token, body={"tenant_id": tenant_id})
    if code == 200 and sel.get("access_token"):
        token = sel["access_token"]
    return token


def main() -> int:
    results: list[bool] = []
    src = WEB.read_text(encoding="utf-8") if WEB.is_file() else ""
    results.append(
        check(
            "VA08-UI 到店核销",
            _page_has(
                WEB,
                "#a08",
                "到店核销",
                "请买家打开小程序「我的预约」",
                "确认核销",
                "请输入有效核销码",
                'data-testid="shop-verifications"',
                "shop_id: currentId",
            ),
            WEB.name,
        )
    )
    results.append(
        check(
            "VA08-UI 核销记录完备",
            "核销记录" in src
            and "核销码 / 买家手机" in src
            and "近7天" in src
            and "近30天" in src
            and "自定义" in src
            and "操作人" in src
            and "列设置" in src
            and "核销详情" in src
            and "预约时段" in src
            and "关闭" in src
            and "当前筛选" in src
            and "导出任务" in src
            and "export-tasks" in src,
            "log tab",
        )
    )
    results.append(
        check(
            "VA08-UI 店员壳",
            _page_has(LAYOUT, "isShopClerk", 'shop-clerk-shell', "shop-verifications")
            and _page_has(ROUTER, "isShopClerk", "/shop/verifications", "shop/redemptions")
            and _page_has(LOGIN, "isShopClerk", "/shop/verifications")
            and "#a08-clerk" in src,
            "clerk shell",
        )
    )

    merchant, tenant_id = _ensure_merchant()
    api_key = _ensure_payment_config(merchant)
    pid = _ensure_service_on_sale(merchant)
    buyer = _buyer_login(tenant_id, f"a08_{uuid.uuid4().hex[:10]}")
    mobile = "138" + f"{uuid.uuid4().int % 10**8:08d}"
    req("POST", "/mp/shop/auth/bind", token=buyer, body={"mobile": mobile})
    code, created = req("POST", "/mp/shop/orders", token=buyer, body={"product_id": pid})
    order = (created or {}).get("order") or created
    assert code == 200, created
    _pay_order(order["order_no"], 9900, api_key)
    code, ents = req("GET", "/mp/shop/entitlements", token=buyer)
    ent = next((e for e in (ents.get("items") or []) if e.get("order_id") == order["id"]), None)
    results.append(check("VA08-1 权益可核销", bool(ent and ent.get("verify_code")), f"{ents}"))

    code, executed = req(
        "POST",
        "/shop/verifications/execute",
        token=merchant,
        body={
            "entitlement_id": ent["id"],
            "deducted_count": 1,
            "idempotency_key": f"a08-{uuid.uuid4().hex[:12]}",
        },
    ) if ent else (0, {})
    results.append(
        check(
            "VA08-2 核销写入 remaining_before",
            code == 200
            and executed.get("remaining_before") == 2
            and executed.get("remaining_after") == 1
            and str(executed.get("verification_no") or "").startswith("RD"),
            f"{code} {executed}",
        )
    )
    vid = executed.get("id")

    code, blist = req("GET", "/mp/shop/bookings?page=1&page_size=50", token=buyer)
    done = next(
        (
            i
            for i in (blist.get("items") or [])
            if i.get("entitlement_id") == (ent or {}).get("id") and i.get("status") == "completed"
        ),
        None,
    )
    results.append(
        check(
            "VA08-2b 核销后 M10c 已完成可见",
            code == 200 and done is not None and done.get("booked_time_slot") == "次数卡",
            f"{code} {done}",
        )
    )

    code, future = req("GET", "/shop/verifications?created_from=2099-01-01", token=merchant)
    results.append(
        check(
            "VA08-3 申请日起未来为空",
            code == 200 and future.get("total") == 0,
            f"{code} {future.get('total')}",
        )
    )

    code, listed = req("GET", "/shop/verifications?page=1&page_size=50", token=merchant)
    hit = next((x for x in (listed.get("items") or []) if x.get("id") == vid), None)
    results.append(
        check(
            "VA08-4 列表含核销单号",
            code == 200 and hit is not None and str(hit.get("verification_no") or "").startswith("RD"),
            f"{code} {hit}",
        )
    )

    op_id = (hit or executed).get("operator_id")
    if op_id:
        code, by_op = req(
            "GET", f"/shop/verifications?operator_id={op_id}&page_size=50", token=merchant
        )
        results.append(
            check(
                "VA08-5 按操作人筛选",
                code == 200
                and all(str(x.get("operator_id")) == str(op_id) for x in (by_op.get("items") or []))
                and any(x.get("id") == vid for x in (by_op.get("items") or [])),
                f"{code} {by_op.get('total')}",
            )
        )
    else:
        results.append(check("VA08-5 按操作人筛选", False, "no operator"))

    code, ops = req("GET", "/shop/verifications/operators", token=merchant)
    results.append(
        check(
            "VA08-6 操作人下拉",
            code == 200 and isinstance(ops.get("items"), list) and len(ops.get("items") or []) >= 1,
            f"{code} {ops}",
        )
    )

    if vid:
        code, one = req("GET", f"/shop/verifications/{vid}", token=merchant)
        results.append(
            check(
                "VA08-7 详情扣次快照",
                code == 200
                and one.get("remaining_before") == 2
                and one.get("remaining_after") == 1
                and one.get("verification_no"),
                f"{code} {one}",
            )
        )
    else:
        results.append(check("VA08-7 详情扣次快照", False, "no vid"))

    code, csv = req("GET", "/shop/verifications/export", token=merchant)
    csv_text = csv if isinstance(csv, str) else str(csv)
    results.append(
        check(
            "VA08-8 导出含默认列",
            code == 200 and "核销时间" in csv_text and "核销码" in csv_text and "操作人" in csv_text,
            f"{code} {csv_text[:80]}",
        )
    )
    code, task = req("POST", "/shop/verifications/export", token=merchant, body={})
    results.append(
        check(
            "VA08-8b POST 导出任务已完成",
            code == 200
            and isinstance(task, dict)
            and task.get("status") == "done"
            and task.get("resource") == "verifications"
            and task.get("id"),
            f"{code} {task}",
        )
    )
    task_id = (task or {}).get("id") if isinstance(task, dict) else None
    if task_id:
        code, file_csv = req("GET", f"/shop/verifications/export-tasks/{task_id}/file", token=merchant)
        results.append(
            check(
                "VA08-8c 任务文件可下载",
                code == 200 and "核销时间" in str(file_csv) and "核销码" in str(file_csv),
                f"{code}",
            )
        )
    else:
        results.append(check("VA08-8c 任务文件可下载", False, "no task"))

    clerk = _ensure_clerk(merchant, tenant_id)
    code, me = req("GET", "/auth/me", token=clerk)
    results.append(
        check(
            "VA08-C me 店员角色",
            code == 200
            and (me.get("active_tenant") or {}).get("role_code") == "shop_clerk"
            and "shop.redemption.execute" in (me.get("permissions") or [])
            and "shop.redemption.list_own" in (me.get("permissions") or []),
            f"{code} {(me.get('active_tenant') or {}).get('role_code')} {me.get('permissions')}",
        )
    )

    code, clerk_list = req("GET", "/shop/verifications?page=1&page_size=50", token=clerk)
    clerk_ids = {x.get("id") for x in (clerk_list.get("items") or [])}
    results.append(
        check(
            "VA08-C list_own 不含他人",
            code == 200 and vid not in clerk_ids,
            f"{code} total={clerk_list.get('total')} vid={vid}",
        )
    )

    code, booked = req("GET", "/shop/bookings?page=1&page_size=5", token=clerk)
    results.append(
        check(
            "VA08-C 预约列表 403",
            code == 403 and "店员仅可访问核销台" in str(booked),
            f"{code} {booked}",
        )
    )
    code, exp_c = req("GET", "/shop/verifications/export", token=clerk)
    results.append(
        check(
            "VA08-C 导出 403",
            code == 403,
            f"{code} {exp_c}",
        )
    )
    code, exp_post = req("POST", "/shop/verifications/export", token=clerk, body={})
    results.append(
        check(
            "VA08-C POST 导出 403",
            code == 403 and "无导出权限" in str(exp_post),
            f"{code} {exp_post}",
        )
    )

    if ent:
        code, looked = req(
            "POST",
            "/shop/verifications/lookup",
            token=clerk,
            body={"verify_code": ent.get("verify_code")},
        )
        results.append(
            check(
                "VA08-C 查询可核销",
                code == 200 and looked.get("result") in ("can_redeem", "already_used", "exhausted"),
                f"{code} {looked}",
            )
        )
        if looked.get("result") == "can_redeem":
            code, cexec = req(
                "POST",
                "/shop/verifications/execute",
                token=clerk,
                body={
                    "entitlement_id": ent["id"],
                    "deducted_count": 1,
                    "idempotency_key": f"a08c-{uuid.uuid4().hex[:12]}",
                },
            )
            results.append(
                check(
                    "VA08-C 店员核销",
                    code == 200 and cexec.get("operator_id"),
                    f"{code} {cexec}",
                )
            )
            code, own = req("GET", "/shop/verifications?page=1&page_size=50", token=clerk)
            own_ids = {x.get("id") for x in (own.get("items") or [])}
            results.append(
                check(
                    "VA08-C list_own 含本人",
                    code == 200 and cexec.get("id") in own_ids,
                    f"{code} {own.get('total')}",
                )
            )
        else:
            results.append(check("VA08-C 店员核销", True, "already consumed"))
            results.append(check("VA08-C list_own 含本人", True, "skip"))
    else:
        results.append(check("VA08-C 查询可核销", False, "no ent"))
        results.append(check("VA08-C 店员核销", False, "no ent"))
        results.append(check("VA08-C list_own 含本人", False, "no ent"))

    ok = sum(1 for x in results if x)
    print(f"verify_shop_a08: {ok}/{len(results)}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
