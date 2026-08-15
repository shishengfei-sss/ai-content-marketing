#!/usr/bin/env python3
"""开票申请列表/抽屉。对照 PRD 01-管理端UI.html #a13 / #a13c / #a13a / #a13b / #a13-select-spec。"""

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
from tests.verify_shop_a14 import _ensure_merchant  # noqa: E402

WEB = REPO_ROOT / "apps" / "web" / "src" / "views" / "shop" / "InvoicesList.vue"
MP = REPO_ROOT / "apps" / "mp" / "src" / "pages" / "shop" / "invoice.vue"


def _page_has(path: Path, *needles: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _paid_course_order(merchant: str, tenant_id: str) -> tuple[dict, str]:
    from tests.http_client import _get_test_client
    from app.database import SessionLocal, uuid_eq
    from app.models.shop import ShopProduct
    from app.services.shop.wechat_pay_service import stub_sign

    api_key = "mock_api_key_a13"
    req(
        "POST",
        "/shop/payment-config",
        token=merchant,
        body={
            "wx_mch_id": "mock_mchid_a13",
            "wx_app_id": "wx_mock_appid_a13",
            "wx_api_key": api_key,
            "wx_notify_url": "http://127.0.0.1:8003/api/v1/mp/shop/payments/notify",
        },
    )
    client = _get_test_client()
    code, col = req(
        "POST", "/shop/columns", token=merchant, body={"title": f"A13专栏-{uuid.uuid4().hex[:6]}"}
    )
    assert code in (200, 201), col
    up = client.post(
        "/api/v1/shop/content/files",
        headers={"Authorization": f"Bearer {merchant}"},
        files={"file": ("a13.mp4", b"v", "video/mp4")},
    ).json()
    code, les = req(
        "POST",
        f"/shop/columns/{col['id']}/lessons",
        token=merchant,
        body={
            "title": "A13课",
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
            "name": f"A13课-{uuid.uuid4().hex[:6]}",
            "price_cents": 19900,
            "cover_url": cover,
            "ref_type": "column",
            "ref_id": col["id"],
        },
    )
    assert code in (200, 201), product
    from uuid import UUID as UUIDType

    db = SessionLocal()
    try:
        p = db.query(ShopProduct).filter(uuid_eq(ShopProduct.id, UUIDType(product["id"]))).first()
        p.status = "on_sale"
        db.commit()
    finally:
        db.close()

    openid = f"a13_{uuid.uuid4().hex[:10]}"
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
    return order, buyer_tok


def main() -> int:
    results: list[bool] = []
    src = WEB.read_text(encoding="utf-8") if WEB.is_file() else ""
    results.append(
        check(
            "VA13-UI 列表完备",
            _page_has(
                WEB,
                "#a13",
                "全部申请",
                "订单号 / 抬头",
                "高级筛选",
                "申请起",
                "申请止",
                "列设置",
                "处理人",
                "开具时间",
                'data-testid="shop-invoices"',
                "shop_id: currentId",
            ),
            WEB.name,
        )
    )
    results.append(
        check(
            "VA13-UI 导出下拉与任务弹窗",
            "当前筛选" in src
            and "导出任务" in src
            and "export-tasks" in src
            and "/shop/invoices/export" in src
            and "ElMessageBox" not in src,
            "export task dialog",
        )
    )
    results.append(
        check(
            "VA13-UI 开具抽屉栏位",
            "抬头（只读）" in src
            and "税号（只读）" in src
            and "邮箱（只读）" in src
            and "金额（只读）" in src
            and "税控开具后填入" in src
            and "电子发票 PDF" in src
            and "ShopMaterialUpload" in src
            and "确认开具" in src
            and 'v-model="issueRemark"' in src
            and "el-input disabled placeholder" not in src,
            "issue drawer",
        )
    )
    results.append(
        check(
            "VA13-UI 驳回弹窗",
            "el-dialog" in src
            and "驳回开票申请" in src
            and "税号与抬头不匹配" in src
            and "金额有误" in src
            and "确认驳回" in src
            and "ElMessageBox" not in src,
            "reject dialog",
        )
    )
    results.append(
        check(
            "VA13-UI 查看抽屉",
            "开票详情" in src
            and "发票号（只读）" in src
            and "开具时间（只读）" in src
            and "审核状态（只读）" in src
            and "驳回原因（只读）" in src
            and "处理人（只读）" in src
            and "备注（只读）" in src,
            "view drawer",
        )
    )
    mp_src = MP.read_text(encoding="utf-8") if MP.is_file() else ""
    results.append(
        check(
            "VA13-UI M13 驳回可重提",
            "#m13" in mp_src
            and "可修改后重提" in mp_src
            and "打开 PDF / 链接" in mp_src
            and "复制发票号" in mp_src,
            MP.name,
        )
    )

    merchant, tenant_id = _ensure_merchant()
    code, future = req("GET", "/shop/invoices?created_from=2099-01-01", token=merchant)
    results.append(
        check(
            "VA13-1 申请起未来日为空",
            code == 200 and future.get("total") == 0,
            f"{code} {future.get('total')}",
        )
    )

    order, buyer_tok = _paid_course_order(merchant, tenant_id)
    tax = "91110000MA01234567"
    code, inv = req(
        "POST",
        "/mp/shop/invoices",
        token=buyer_tok,
        body={
            "order_id": order["id"],
            "title_type": "company",
            "title": "北京验收科技有限公司",
            "tax_no": tax,
            "email": "a13@example.com",
        },
    )
    results.append(
        check(
            "VA13-2 买家提交企业开票",
            code in (200, 201) and inv.get("title_type") == "company",
            f"{code} {inv}",
        )
    )
    inv_id = inv.get("id")

    code, companies = req("GET", "/shop/invoices?title_type=company&page_size=100", token=merchant)
    company_rows = companies.get("items") or []
    results.append(
        check(
            "VA13-3 类型=企业",
            code == 200
            and all(x.get("title_type") == "company" for x in company_rows)
            and any(x.get("id") == inv_id for x in company_rows),
            f"{code} {len(company_rows)} {inv_id}",
        )
    )

    code, csv = req("GET", "/shop/invoices/export", token=merchant)
    csv_text = csv if isinstance(csv, str) else str(csv)
    results.append(
        check(
            "VA13-4 导出含订单与中文状态",
            code == 200 and "订单" in csv_text and ("待处理" in csv_text or "已开票" in csv_text),
            f"{code} {csv_text[:80]}",
        )
    )
    code, task = req("POST", "/shop/invoices/export", token=merchant, body={})
    task_id = task.get("id") if isinstance(task, dict) else None
    results.append(
        check(
            "VA13-4b POST 导出任务已完成",
            code == 200
            and task.get("status") == "done"
            and task.get("resource") == "invoices"
            and int(task.get("row_count") or 0) >= 1
            and bool(task_id),
            f"{code} {task}",
        )
    )
    if task_id:
        code, file_csv = req("GET", f"/shop/invoices/export-tasks/{task_id}/file", token=merchant)
        file_text = file_csv if isinstance(file_csv, str) else str(file_csv)
        results.append(
            check(
                "VA13-4c 任务文件可下载",
                code == 200 and "订单" in file_text and ("待处理" in file_text or "已开票" in file_text),
                f"{code} {file_text[:80]}",
            )
        )
        code, meta = req("GET", f"/shop/invoices/export-tasks/{task_id}", token=merchant)
        results.append(
            check(
                "VA13-4d 任务详情",
                code == 200 and meta.get("id") == task_id and meta.get("status") == "done",
                f"{code} {meta}",
            )
        )
    else:
        results.append(check("VA13-4c 任务文件可下载", False, "no task"))
        results.append(check("VA13-4d 任务详情", False, "no task"))

    if inv_id:
        inv_no = f"INV{uuid.uuid4().hex[:10].upper()}"
        remark = "税控已开具，电子票已传"
        code, issued = req(
            "POST",
            f"/shop/invoices/{inv_id}/issue",
            token=merchant,
            body={"invoice_no": inv_no, "remark": remark},
        )
        results.append(
            check(
                "VA13-5 开具后处理人",
                code == 200
                and issued.get("status") == "issued"
                and issued.get("invoice_no") == inv_no
                and issued.get("remark") == remark
                and bool(issued.get("operator_name")),
                f"{code} {issued}",
            )
        )
        code, one = req("GET", f"/shop/invoices/{inv_id}", token=merchant)
        results.append(
            check(
                "VA13-6 详情含处理人开具时间",
                code == 200
                and one.get("operator_name")
                and one.get("issued_at")
                and one.get("invoice_no") == inv_no
                and one.get("remark") == remark,
                f"{code} {one}",
            )
        )
        code, again = req(
            "POST",
            "/mp/shop/invoices",
            token=buyer_tok,
            body={
                "order_id": order["id"],
                "title_type": "company",
                "title": "北京验收科技有限公司",
                "tax_no": tax,
                "email": "a13@example.com",
            },
        )
        results.append(
            check(
                "VA13-7 已开票不可重提",
                code == 409,
                f"{code} {again}",
            )
        )
    else:
        results.append(check("VA13-5 开具后处理人", False, "no inv"))
        results.append(check("VA13-6 详情含处理人开具时间", False, "no inv"))
        results.append(check("VA13-7 已开票不可重提", False, "no inv"))

    order2, buyer2 = _paid_course_order(merchant, tenant_id)
    code, inv2 = req(
        "POST",
        "/mp/shop/invoices",
        token=buyer2,
        body={
            "order_id": order2["id"],
            "title_type": "company",
            "title": "广州某某科技有限公司",
            "tax_no": "91440101MA5XXXXXX1",
            "email": "old@example.com",
        },
    )
    inv2_id = inv2.get("id") if code in (200, 201) else None
    if inv2_id:
        code, rej = req(
            "POST",
            f"/shop/invoices/{inv2_id}/reject",
            token=merchant,
            body={"reason": "税号栏为空，企业抬头须填税号"},
        )
        results.append(
            check(
                "VA13-8 驳回后可查看原因",
                code == 200
                and rej.get("status") == "rejected"
                and "税号栏为空" in (rej.get("reject_reason") or ""),
                f"{code} {rej}",
            )
        )
        code, ret = req(
            "POST",
            "/mp/shop/invoices",
            token=buyer2,
            body={
                "order_id": order2["id"],
                "title_type": "company",
                "title": "广州某某科技股份有限公司",
                "tax_no": "91440101MA5XXXXXX2",
                "email": "finance@example.com",
            },
        )
        results.append(
            check(
                "VA13-9 驳回后重提同一申请",
                code in (200, 201)
                and ret.get("id") == inv2_id
                and ret.get("status") == "submitted"
                and ret.get("title") == "广州某某科技股份有限公司"
                and ret.get("tax_no") == "91440101MA5XXXXXX2"
                and ret.get("email") == "finance@example.com"
                and not ret.get("reject_reason"),
                f"{code} {ret}",
            )
        )
        code, listed = req(
            "GET",
            f"/shop/invoices?q={order2['order_no']}&page_size=20",
            token=merchant,
        )
        rows = listed.get("items") or []
        same = [x for x in rows if x.get("id") == inv2_id]
        results.append(
            check(
                "VA13-10 重提后商家见待处理且无重复行",
                code == 200
                and len(same) == 1
                and same[0].get("status") == "submitted"
                and same[0].get("title") == "广州某某科技股份有限公司",
                f"{code} n={len(same)} {same[:1]}",
            )
        )
    else:
        results.append(check("VA13-8 驳回后可查看原因", False, f"{code} {inv2}"))
        results.append(check("VA13-9 驳回后重提同一申请", False, "no inv2"))
        results.append(check("VA13-10 重提后商家见待处理且无重复行", False, "no inv2"))

    ok = sum(1 for x in results if x)
    print(f"verify_shop_a13: {ok}/{len(results)}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
