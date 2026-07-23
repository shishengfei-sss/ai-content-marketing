#!/usr/bin/env python3
"""订单增强：完成/撤回/取消拦回款/毛利/复制/批量/导出。"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.verify_crm_helpers import (  # noqa: E402
    admin_token,
    check,
    ensure_crm_test_users,
    finish_phase,
    req,
)


def main() -> int:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
    finally:
        db.close()

    tok = admin_token()
    results: list[bool] = []

    code, cust = req(
        "POST",
        "/crm/customers",
        token=tok,
        body={"company_name": f"OrdEnh客户-{uuid.uuid4().hex[:6]}", "mobile": f"139{uuid.uuid4().hex[:8]}"[:11]},
    )
    results.append(check("pre 创建客户", code == 201, str(code)))
    cust_id = (cust or {}).get("id")

    code, prod = req(
        "POST",
        "/crm/products",
        token=tok,
        body={
            "name": f"毛利产品-{uuid.uuid4().hex[:6]}",
            "list_price": 100,
            "cost_price": 40,
            "unit": "套",
        },
    )
    results.append(check("pre 创建产品", code in (200, 201), str(code)))
    prod_id = (prod or {}).get("id")

    code, order = req(
        "POST",
        "/crm/orders",
        token=tok,
        body={
            "title": f"增强订单-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "source": "deal",
            "lines": [
                {
                    "product_id": prod_id,
                    "name": "毛利产品",
                    "quantity": 2,
                    "unit_price": 100,
                    "discount_rate": 0,
                }
            ],
        },
    )
    results.append(check("1 创建订单", code == 201, str(code)))
    oid = (order or {}).get("id")
    results.append(
        check(
            "1b 毛利字段",
            float((order or {}).get("cost_total") or 0) == 80.0
            and float((order or {}).get("margin_amount") or 0) == 120.0
            and abs(float((order or {}).get("margin_rate") or 0) - 60.0) < 0.01,
            str({k: (order or {}).get(k) for k in ("amount", "cost_total", "margin_amount", "margin_rate")}),
        )
    )

    code, patched = req("PATCH", f"/crm/orders/{oid}", token=tok, body={"status": "confirmed", "title": order["title"]})
    # status 已从 OrderUpdate 移除 → pydantic 忽略多余字段 → 仍 draft
    results.append(
        check(
            "2 PATCH 忽略 status 仍 draft",
            code == 200 and (patched or {}).get("status") == "draft",
            f"{code} {(patched or {}).get('status')}",
        )
    )

    code, submitted = req("POST", f"/crm/orders/{oid}/submit", token=tok)
    results.append(
        check(
            "3 submit→confirmed(无规则或直过)",
            code == 200 and (submitted or {}).get("status") in ("confirmed", "pending_approval"),
            f"{code} {(submitted or {}).get('status')}",
        )
    )
    # 若进了审批，先通过
    if (submitted or {}).get("status") == "pending_approval":
        code, submitted = req("POST", f"/crm/orders/{oid}/approve", token=tok)
        results.append(check("3b approve→confirmed", code == 200 and (submitted or {}).get("status") == "confirmed", str(code)))

    code, cloned = req("POST", f"/crm/orders/{oid}/clone", token=tok)
    results.append(
        check(
            "4 clone draft",
            code == 201 and (cloned or {}).get("status") == "draft" and (cloned or {}).get("id") != oid,
            str(code),
        )
    )
    code, tmpl = req("POST", f"/crm/orders/{oid}/clone?as_template=true", token=tok)
    results.append(
        check(
            "5 clone as_template",
            code == 201 and ((tmpl or {}).get("extra_data") or {}).get("is_template") is True,
            str((tmpl or {}).get("extra_data")),
        )
    )

    code, done = req("POST", f"/crm/orders/{oid}/complete", token=tok)
    results.append(check("6 complete", code == 200 and (done or {}).get("status") == "completed", str(code)))

    # 撤回：独立订单（无规则时 409）
    code, o2 = req(
        "POST",
        "/crm/orders",
        token=tok,
        body={
            "title": f"撤回测-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "source": "deal",
            "lines": [{"name": "项", "quantity": 1, "unit_price": 10}],
        },
    )
    oid2 = (o2 or {}).get("id")
    code, pending = req("POST", f"/crm/orders/{oid2}/submit", token=tok)
    if (pending or {}).get("status") == "pending_approval":
        code, wd = req("POST", f"/crm/orders/{oid2}/withdraw", token=tok)
        results.append(check("7 withdraw→draft", code == 200 and (wd or {}).get("status") == "draft", str(code)))
    else:
        code, wd = req("POST", f"/crm/orders/{oid2}/withdraw", token=tok)
        results.append(check("7 withdraw 非待审→409", code == 409, str(code)))

    code, o3 = req(
        "POST",
        "/crm/orders",
        token=tok,
        body={
            "title": f"批量A-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "source": "deal",
            "lines": [{"name": "A", "quantity": 1, "unit_price": 1}],
        },
    )
    code, o4 = req(
        "POST",
        "/crm/orders",
        token=tok,
        body={
            "title": f"批量B-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "source": "deal",
            "lines": [{"name": "B", "quantity": 1, "unit_price": 1}],
        },
    )
    ids = [(o3 or {}).get("id"), (o4 or {}).get("id")]
    code, batch = req(
        "POST",
        "/crm/orders/batch-action",
        token=tok,
        body={"order_ids": ids, "action": "confirm"},
    )
    results.append(
        check("8 batch confirm", code == 200 and (batch or {}).get("succeeded", 0) >= 1, str(batch))
    )

    code, o5 = req(
        "POST",
        "/crm/orders",
        token=tok,
        body={
            "title": f"回款拦-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "source": "deal",
            "lines": [{"name": "C", "quantity": 1, "unit_price": 50}],
        },
    )
    oid5 = (o5 or {}).get("id")
    req("POST", f"/crm/orders/{oid5}/submit", token=tok)
    # 若 pending，approve
    code, cur = req("GET", f"/crm/orders/{oid5}", token=tok)
    if (cur or {}).get("status") == "pending_approval":
        req("POST", f"/crm/orders/{oid5}/approve", token=tok)
    code, pay = req(
        "POST",
        "/crm/payments",
        token=tok,
        body={"order_id": oid5, "amount": 50, "method": "bank", "status": "pending"},
    )
    pay_id = (pay or {}).get("id")
    if pay_id:
        req("POST", f"/crm/payments/{pay_id}/confirm", token=tok)
    code, _ = req("POST", f"/crm/orders/{oid5}/cancel", token=tok)
    results.append(check("9 有确认回款不可取消", code == 409, str(code)))

    code, export_body = req("GET", "/crm/export/orders?format=csv", token=tok)
    results.append(
        check(
            "10 export orders csv",
            code == 200 and (isinstance(export_body, str) or isinstance(export_body, (bytes, dict))),
            f"{code} type={type(export_body)}",
        )
    )

    return finish_phase("order-ops-enhance", results)


if __name__ == "__main__":
    raise SystemExit(main())
