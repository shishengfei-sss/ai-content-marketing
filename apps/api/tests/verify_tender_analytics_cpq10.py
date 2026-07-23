#!/usr/bin/env python3
"""v1.3 P1：招标线索看板 FR-TENDER-09 + Deal/线索唤起 CPQ FR-CPQ-10。"""
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from tests.http_client import check, req
from tests.verify_crm_helpers import finish_phase


def alembic_current() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    return (proc.stdout or "") + (proc.stderr or "")


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []
    out = alembic_current()
    results.append(check(f"VA10-0 alembic={EXPECTED_HEAD}", is_at_expected_head(out), out.strip()[:200]))

    tok = login("13900000099", "test123456")
    tag = uuid.uuid4().hex[:6]

    code, analytics = req("GET", "/crm/tender-lead-analytics", token=tok)
    results.append(
        check(
            "VA10-1 看板 200 含核心字段",
            code == 200
            and isinstance(analytics, dict)
            and "follow_rate" in analytics
            and "conversion_rate" in analytics
            and "high_match_rate" in analytics
            and "score_buckets" in analytics,
            f"{code} keys={list((analytics or {}).keys())[:12]}",
        )
    )

    # 找一个客户
    code, custs = req("GET", "/crm/customers?page=1&page_size=5", token=tok)
    customer_id = None
    if code == 200 and (custs or {}).get("items"):
        customer_id = custs["items"][0]["id"]
    results.append(check("VA10-2 有客户可报价", bool(customer_id), f"{code}"))

    # CPQ 产品（无则创建）
    code, products = req("GET", "/crm/cpq/products", token=tok)
    product_id = None
    if code == 200 and isinstance(products, list) and products:
        product_id = products[0]["id"]
    if not product_id:
        code, product = req(
            "POST",
            "/crm/products",
            token=tok,
            body={
                "name": f"CPQ联动泵-{tag}",
                "list_price": 10000,
                "cost_price": 6000,
                "cpq_enabled": True,
                "is_active": True,
            },
        )
        product_id = (product or {}).get("id")
        results.append(check("VA10-3 创建 CPQ 产品", code in (200, 201) and bool(product_id), f"{code}"))
    else:
        results.append(check("VA10-3 有 CPQ 产品", True, product_id))

    # 未 claim 的 tender_lead_id 不可报价
    code, listed = req("GET", "/crm/tender-leads?status=pending&page_size=5", token=tok)
    pending = ((listed or {}).get("items") or [None])[0]
    if pending and customer_id and product_id:
        code, denied = req(
            "POST",
            "/crm/cpq/quotes",
            token=tok,
            body={
                "customer_id": customer_id,
                "subject": f"禁报-{tag}",
                "product_id": product_id,
                "quantity": 1,
                "selected_params": {},
                "scored_tender_lead_id": pending["id"],
                "confirm_low_margin": True,
            },
        )
        results.append(
            check(
                "VA10-4 未纳入线索不可带 tender 报价",
                code == 400,
                f"{code} {denied}",
            )
        )
    else:
        results.append(check("VA10-4 未纳入线索不可带 tender 报价（跳过无 pending）", True, "skip"))

    # Deal 唤起：带 deal_id + 匹配客户
    code, deals = req("GET", "/crm/deals?page=1&page_size=10", token=tok)
    deal = None
    for d in (deals or {}).get("items") or []:
        if d.get("customer_id") and d.get("status") != "lost":
            deal = d
            break
    if deal and product_id:
        # 客户不一致应 400
        other_cust = customer_id if customer_id != deal["customer_id"] else None
        if not other_cust and (custs or {}).get("items") and len(custs["items"]) > 1:
            other_cust = next(
                (c["id"] for c in custs["items"] if c["id"] != deal["customer_id"]),
                None,
            )
        if other_cust:
            code, mismatch = req(
                "POST",
                "/crm/cpq/quotes",
                token=tok,
                body={
                    "customer_id": other_cust,
                    "deal_id": deal["id"],
                    "subject": f"错配-{tag}",
                    "product_id": product_id,
                    "quantity": 1,
                    "selected_params": {},
                    "confirm_low_margin": True,
                },
            )
            results.append(check("VA10-5 deal/客户不一致拒写", code == 400, f"{code} {mismatch}"))
        else:
            results.append(check("VA10-5 deal/客户不一致拒写（仅一客户跳过）", True, "skip"))

        code, ok = req(
            "POST",
            "/crm/cpq/quotes",
            token=tok,
            body={
                "customer_id": deal["customer_id"],
                "deal_id": deal["id"],
                "subject": f"Deal唤起CPQ-{tag}",
                "product_id": product_id,
                "quantity": 1,
                "selected_params": {},
                "confirm_low_margin": True,
            },
        )
        snap = (ok or {}).get("cpq_config_snapshot") or {}
        results.append(
            check(
                "VA10-6 Deal 唤起 CPQ 写入 quotes",
                code in (200, 201) and bool((ok or {}).get("id")) and snap.get("deal_id") == deal["id"],
                f"{code} snap_deal={snap.get('deal_id')}",
            )
        )
    else:
        results.append(check("VA10-5 deal/客户不一致拒写（无商机跳过）", True, "skip"))
        results.append(check("VA10-6 Deal 唤起 CPQ 写入 quotes（无商机跳过）", True, "skip"))

    return finish_phase("v1.3-analytics-cpq10", results)


if __name__ == "__main__":
    raise SystemExit(main())
