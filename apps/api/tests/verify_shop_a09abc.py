#!/usr/bin/env python3
"""A09-A/B/C 关单/退款/重发弹窗规格验收。对照 PRD 01-管理端UI.html #a09a #a09b #a09c。"""

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

WEB = REPO_ROOT / "apps" / "web" / "src"
COMP = WEB / "components" / "shop" / "OrderActionDialogs.vue"
LIST = WEB / "views" / "shop" / "OrdersList.vue"
DETAIL = WEB / "views" / "shop" / "OrderDetail.vue"


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
        parts = []
        for x in d:
            if isinstance(x, dict):
                parts.append(str(x.get("msg") or x.get("message") or x))
            else:
                parts.append(str(x))
        return " ".join(parts)
    return str(d)


def _ensure_merchant() -> tuple[str, str]:
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
                    "tenant_name": f"A09验-{uuid.uuid4().hex[:6]}",
                    "display_name": "A09验",
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
    api_key = "mock_api_key_a09"
    code, data = req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_a09",
            "wx_app_id": "wx_mock_appid_a09",
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
        body={"title": f"A09col-{uuid.uuid4().hex[:6]}", "intro": "d"},
    )
    assert code in (200, 201), col
    code, les = req(
        "POST",
        f"/shop/columns/{col['id']}/lessons",
        token=merchant,
        body={
            "title": "L1",
            "duration_sec": 60,
            "sort_order": 1,
            "media_type": "video",
            "media_url": "https://example.com/a09.mp4",
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
            "name": f"A09课-{uuid.uuid4().hex[:6]}",
            "price_cents": 19900,
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


def _create_order(merchant: str, tenant_id: str, product_id: str, *, pay: bool, api_key: str):
    from app.services.shop.wechat_pay_service import stub_sign

    openid = f"a09_{uuid.uuid4().hex[:10]}"
    code, bl = req(
        "POST", "/mp/shop/auth/login", body={"tenant_id": tenant_id, "code": f"mock:{openid}"}
    )
    assert code == 200, bl
    buyer_tok = bl["access_token"]
    mobile = "139" + f"{uuid.uuid4().int % 10**8:08d}"
    req("POST", "/mp/shop/auth/bind", token=buyer_tok, body={"mobile": mobile})
    code, created = req(
        "POST", "/mp/shop/orders", token=buyer_tok, body={"product_id": product_id}
    )
    assert code in (200, 201), created
    order = (created or {}).get("order") or created
    if pay:
        tx = f"TX{uuid.uuid4().hex[:16]}"
        sign = stub_sign(order["order_no"], tx, int(order["amount_cents"]), api_key)
        code, n = req(
            "POST",
            "/mp/shop/payments/notify",
            body={
                "order_no": order["order_no"],
                "transaction_id": tx,
                "paid_amount_cents": int(order["amount_cents"]),
                "sign": sign,
            },
        )
        assert code == 200, n
        code, order = req("GET", f"/shop/orders/{order['id']}", token=merchant)
        assert code == 200, order
    return order


def main() -> int:
    results: list[bool] = []
    results.append(
        check(
            "VA09-UI-1 弹窗组件含原因枚举",
            _page_has(
                COMP,
                "关闭原因",
                "退款原因",
                "buyer_abandon",
                "wrong_duplicate",
                "buyer_request",
                "fulfill_dispute",
                "确认关闭",
                "提交退款",
                "确认发送",
                "将占用 1 条领权短信额度",
                "本订单已开具发票",
            ),
            str(COMP),
        )
    )
    results.append(
        check(
            "VA09-UI-2 列表/详情接入弹窗",
            _page_has(LIST, "OrderActionDialogs", "openClose")
            and _page_has(DETAIL, "OrderActionDialogs", "openRefund"),
            f"{LIST.exists()} {DETAIL.exists()}",
        )
    )
    list_src = LIST.read_text(encoding="utf-8") if LIST.is_file() else ""
    results.append(
        check(
            "VA09-UI-3 导出下拉与任务弹窗",
            "当前筛选" in list_src
            and "列配置" in list_src
            and "导出任务" in list_src
            and "export-tasks" in list_src
            and "/shop/orders/export" in list_src
            and "ElMessageBox" not in list_src,
            "export task dialog",
        )
    )

    merchant, tenant_id = _ensure_merchant()
    api_key = _ensure_payment(merchant)
    product_id = _on_sale_product(merchant)

    pending = _create_order(merchant, tenant_id, product_id, pay=False, api_key=api_key)
    code, r = req("POST", f"/shop/orders/{pending['id']}/close", token=merchant, body={})
    results.append(
        check(
            "VA09-A-1 无原因 422",
            code == 422 and ("关闭原因" in _err_text(r) or "reason" in _err_text(r).lower()),
            f"{code} {_err_text(r)}",
        )
    )
    code, r = req(
        "POST",
        f"/shop/orders/{pending['id']}/close",
        token=merchant,
        body={"reason_code": "other", "reason_text": "短"},
    )
    results.append(
        check(
            "VA09-A-2 other 短说明 422",
            code == 422 and "4" in _err_text(r),
            f"{code} {_err_text(r)}",
        )
    )
    code, closed = req(
        "POST",
        f"/shop/orders/{pending['id']}/close",
        token=merchant,
        body={"reason_code": "buyer_abandon"},
    )
    results.append(
        check(
            "VA09-A-3 买家放弃关闭",
            code == 200
            and closed.get("status") == "closed"
            and "买家放弃" in (closed.get("refund_reason") or ""),
            f"{code} {closed.get('status')} {closed.get('refund_reason')}",
        )
    )

    paid = _create_order(merchant, tenant_id, product_id, pay=True, api_key=api_key)
    code, r = req("POST", f"/shop/orders/{paid['id']}/refund", token=merchant, body={})
    results.append(
        check(
            "VA09-B-1 无原因 422",
            code == 422 and ("退款原因" in _err_text(r) or "reason" in _err_text(r).lower()),
            f"{code} {_err_text(r)}",
        )
    )
    code, r = req(
        "POST",
        f"/shop/orders/{paid['id']}/refund",
        token=merchant,
        body={"reason_code": "other", "remark": "啊"},
    )
    results.append(
        check(
            "VA09-B-2 other 短说明 422",
            code == 422 and "4" in _err_text(r),
            f"{code} {_err_text(r)}",
        )
    )
    code, ref = req(
        "POST",
        f"/shop/orders/{paid['id']}/refund",
        token=merchant,
        body={"reason_code": "buyer_request", "remark": "验收退款"},
    )
    results.append(
        check(
            "VA09-B-3 买家申请全额退",
            code == 200 and "买家申请" in (ref.get("reason") or ""),
            f"{code} {ref.get('status')} {ref.get('reason')}",
        )
    )

    code, rn = req(
        "POST", f"/shop/orders/{paid['id']}/resend-notify", token=merchant, body={}
    )
    results.append(
        check(
            "VA09-C-1 非待领权重发拒绝",
            code == 422 and "待领权" in _err_text(rn),
            f"{code} {_err_text(rn)}",
        )
    )

    from uuid import UUID as UUIDType

    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopOrder

    claim_order = _create_order(merchant, tenant_id, product_id, pay=True, api_key=api_key)
    db = SessionLocal()
    try:
        o = db.query(ShopOrder).filter(uuid_eq(ShopOrder.id, UUIDType(claim_order["id"]))).first()
        o.status = "claim_pending"
        db.commit()
    finally:
        db.close()
    code, rn = req(
        "POST", f"/shop/orders/{claim_order['id']}/resend-notify", token=merchant, body={}
    )
    results.append(
        check("VA09-C-2 待领权重发成功", code == 200 and rn.get("ok") is True, f"{code} {rn}")
    )

    code_ex, csv_body = req("GET", "/shop/orders/export", token=merchant)
    results.append(
        check(
            "VA09-X-1 GET 导出 CSV",
            code_ex == 200 and "单号" in str(csv_body),
            f"{code_ex}",
        )
    )
    code, task = req("POST", "/shop/orders/export", token=merchant, body={})
    results.append(
        check(
            "VA09-X-2 POST 导出任务已完成",
            code == 200
            and isinstance(task, dict)
            and task.get("status") == "done"
            and task.get("resource") == "orders"
            and task.get("id"),
            f"{code} {task}",
        )
    )
    task_id = (task or {}).get("id") if isinstance(task, dict) else None
    if task_id:
        code, file_csv = req("GET", f"/shop/orders/export-tasks/{task_id}/file", token=merchant)
        csv_text = str(file_csv)
        results.append(
            check(
                "VA09-X-3 任务文件可下载",
                code == 200 and "单号" in csv_text and ("已关闭" in csv_text or "已退款" in csv_text),
                f"{code}",
            )
        )
        code, meta = req("GET", f"/shop/orders/export-tasks/{task_id}", token=merchant)
        results.append(
            check(
                "VA09-X-4 任务详情",
                code == 200 and meta.get("status") == "done" and int(meta.get("row_count") or 0) >= 1,
                f"{code} {meta}",
            )
        )
        code, col_task = req(
            "POST",
            "/shop/orders/export",
            token=merchant,
            body={"columns": ["order_no", "status"]},
        )
        results.append(
            check(
                "VA09-X-5 列配置仅含所选列",
                code == 200 and col_task.get("status") == "done" and col_task.get("id"),
                f"{code} {col_task}",
            )
        )
        col_id = (col_task or {}).get("id") if isinstance(col_task, dict) else None
        if col_id:
            code, col_csv = req("GET", f"/shop/orders/export-tasks/{col_id}/file", token=merchant)
            head = str(col_csv).splitlines()[0] if col_csv else ""
            results.append(
                check(
                    "VA09-X-6 列配置 CSV 表头",
                    code == 200 and "单号" in head and "状态" in head and "买家昵称" not in head,
                    f"{code} {head}",
                )
            )
        else:
            results.append(check("VA09-X-6 列配置 CSV 表头", False, "no col task"))
    else:
        results.append(check("VA09-X-3 任务文件可下载", False, "no task"))
        results.append(check("VA09-X-4 任务详情", False, "no task"))
        results.append(check("VA09-X-5 列配置仅含所选列", False, "no task"))
        results.append(check("VA09-X-6 列配置 CSV 表头", False, "no task"))

    passed = sum(1 for x in results if x)
    print(f"\n{passed}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
