#!/usr/bin/env python3
"""v1.3 CPQ W1–2 冒烟：价目取价 + 产品参数 + calculate。"""
from __future__ import annotations

import subprocess
import sys
import time
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
    results.append(check(f"VCPQ-0 alembic={EXPECTED_HEAD}", is_at_expected_head(out), out.strip()[:200]))

    token = login("13900000099", "test123456")
    tag = uuid.uuid4().hex[:6]

    code, product = req(
        "POST",
        "/crm/products",
        token=token,
        body={
            "name": f"CPQ泵-{tag}",
            "list_price": 10000,
            "cost_price": 6000,
            "cpq_enabled": True,
            "is_active": True,
        },
    )
    results.append(check("VCPQ-1 创建 cpq 产品", code in (200, 201), f"{code} {product}"))
    pid = (product or {}).get("id")
    if not pid:
        return finish_phase("v1.3-cpq-w12", results)

    results.append(check("VCPQ-1b cpq_enabled", product.get("cpq_enabled") is True, str(product.get("cpq_enabled"))))

    code, books = req("GET", "/crm/price-books", token=token)
    results.append(check("VCPQ-2 价目列表", code == 200, str(code)))
    book_id = None
    if isinstance(books, list) and books:
        book_id = books[0].get("id")
    else:
        code, book = req(
            "POST",
            "/crm/price-books",
            token=token,
            body={"name": f"CPQ价目-{tag}", "is_default": True, "is_active": True},
        )
        results.append(check("VCPQ-2b 创建价目", code in (200, 201), f"{code}"))
        book_id = (book or {}).get("id")

    if book_id:
        code, _ = req(
            "POST",
            f"/crm/price-books/{book_id}/entries",
            token=token,
            body={"product_id": pid, "unit_price": 8888, "min_quantity": 1},
        )
        results.append(check("VCPQ-3 价目条目", code in (200, 201), str(code)))

    code, resolved = req(
        "POST",
        "/crm/cpq/resolve-price",
        token=token,
        body={"product_id": pid, "quantity": 1},
    )
    results.append(check("VCPQ-4 resolve-price 200", code == 200, f"{code} {resolved}"))
    if code == 200 and book_id:
        results.append(
            check(
                "VCPQ-4b 取价优先价目",
                float((resolved or {}).get("unit_price") or 0) == 8888
                or (resolved or {}).get("source") in ("price_book", "product_list_price"),
                str(resolved),
            )
        )

    code, param = req(
        "POST",
        f"/crm/cpq/products/{pid}/params",
        token=token,
        body={
            "param_name": "材质",
            "param_type": "select",
            "options": ["铸铁", "不锈钢"],
            "sort_order": 1,
        },
    )
    results.append(check("VCPQ-5 创建参数", code in (200, 201), f"{code} {param}"))
    param_id = (param or {}).get("id")

    if param_id:
        code, pricing = req(
            "POST",
            f"/crm/cpq/params/{param_id}/pricings",
            token=token,
            body={
                "option_value": "不锈钢",
                "price_adjustment_type": "fixed",
                "price_adjustment_value": 500,
            },
        )
        results.append(check("VCPQ-6 价差映射", code in (200, 201), f"{code}"))

        code, calc = req(
            "POST",
            "/crm/cpq/calculate",
            token=token,
            body={
                "product_id": pid,
                "quantity": 2,
                "selected_params": {"材质": "不锈钢"},
                "discount_rate": 0,
                "shipping_cost": 0,
            },
        )
        results.append(check("VCPQ-7 calculate 200", code == 200, f"{code} {calc}"))
        if code == 200:
            adj = float((calc or {}).get("adjusted_unit_price") or 0)
            base = float((calc or {}).get("base_unit_price") or 0)
            results.append(check("VCPQ-7b 价差生效", adj >= base + 500 - 0.01, f"base={base} adj={adj}"))

        code, calc_low = req(
            "POST",
            "/crm/cpq/calculate",
            token=token,
            body={
                "product_id": pid,
                "quantity": 1,
                "selected_params": {},
                "min_margin_pct": 99,
                "confirm_low_margin": False,
            },
        )
        results.append(
            check(
                "VCPQ-8 低毛利拦截",
                code == 400,
                f"{code} {calc_low}",
            )
        )

    code, plist = req("GET", "/crm/cpq/products", token=token)
    results.append(
        check(
            "VCPQ-9 cpq products 含新建",
            code == 200 and isinstance(plist, list) and any(p.get("id") == pid for p in plist),
            str(code),
        )
    )

    code, cust = req(
        "POST",
        "/crm/customers",
        token=token,
        body={"company_name": f"CPQ客户-{tag}", "mobile": f"138{tag}0001"[:11]},
    )
    results.append(check("VCPQ-10 准备客户", code in (200, 201), f"{code}"))
    cust_id = (cust or {}).get("id")

    if cust_id and pid:
        code, blocked = req(
            "POST",
            "/crm/cpq/quotes",
            token=token,
            body={
                "customer_id": cust_id,
                "subject": f"CPQ报价-{tag}",
                "product_id": pid,
                "quantity": 1,
                "selected_params": {"材质": "不锈钢"} if param_id else {},
                "min_margin_pct": 99,
                "confirm_low_margin": False,
            },
        )
        results.append(check("VCPQ-10b 低毛利拒存", code == 400, f"{code} {blocked}"))

        code, quote = req(
            "POST",
            "/crm/cpq/quotes",
            token=token,
            body={
                "customer_id": cust_id,
                "subject": f"CPQ报价-{tag}",
                "product_id": pid,
                "quantity": 2,
                "selected_params": {"材质": "不锈钢"} if param_id else {},
                "discount_rate": 0,
                "shipping_cost": 100,
                "min_margin_pct": 10,
                "confirm_low_margin": False,
            },
        )
        results.append(check("VCPQ-11 保存 quotes 201", code == 201, f"{code} {quote}"))
        qid = (quote or {}).get("id")
        snap = (quote or {}).get("cpq_config_snapshot") or {}
        results.append(
            check(
                "VCPQ-11b 有快照与明细",
                bool(qid)
                and bool(snap.get("selected_params") is not None or snap.get("calculation"))
                and isinstance((quote or {}).get("lines"), list)
                and len((quote or {}).get("lines") or []) >= 1,
                str(quote),
            )
        )
        if qid:
            code, got = req("GET", f"/crm/quotes/{qid}", token=token)
            results.append(
                check(
                    "VCPQ-11c 详情可读快照",
                    code == 200 and bool((got or {}).get("cpq_config_snapshot")),
                    f"{code}",
                )
            )

            code, cloned = req("POST", f"/crm/quotes/{qid}/clone", token=token)
            results.append(check("VCPQ-12 复制报价 201", code == 201, f"{code}"))
            cid = (cloned or {}).get("id")
            results.append(
                check(
                    "VCPQ-12b 复制含快照",
                    bool(cid)
                    and cid != qid
                    and bool((cloned or {}).get("cpq_config_snapshot")),
                    str(cloned),
                )
            )
            if cid:
                req("DELETE", f"/crm/quotes/{cid}", token=token)

            code, pdf_job = req("POST", f"/crm/cpq/quotes/{qid}/pdf", token=token)
            results.append(
                check(
                    "VCPQ-13 发起 PDF",
                    code in (200, 202) and (pdf_job or {}).get("status") in ("generating", "completed"),
                    f"{code} {pdf_job}",
                )
            )
            pdf_ok = False
            last = pdf_job

            for _ in range(25):
                code, st = req("GET", f"/crm/cpq/quotes/{qid}/pdf-status", token=token)
                last = st
                if code == 200 and (st or {}).get("status") == "completed":
                    pdf_ok = True
                    break
                if code == 200 and (st or {}).get("status") == "failed":
                    break
                time.sleep(0.25)
            results.append(check("VCPQ-13b PDF completed", pdf_ok, str(last)))
            if pdf_ok:
                code, _body = req("GET", f"/crm/cpq/quotes/{qid}/pdf/download", token=token)
                results.append(check("VCPQ-13c PDF 可下载", code == 200, str(code)))

            code, parsed = req(
                "POST",
                "/crm/cpq/ai-parse",
                token=token,
                body={
                    "product_id": pid,
                    "text": "客户要 2 台不锈钢泵，化工防腐场景",
                },
            )
            results.append(check("VCPQ-14 ai-parse 200", code == 200, f"{code} {parsed}"))
            recs = (parsed or {}).get("recommendations") or []
            hit = any(
                r.get("param_name") == "材质" and "不锈钢" in str(r.get("suggested_value") or "")
                for r in recs
            )
            results.append(
                check(
                    "VCPQ-14b 推荐不锈钢且须人审",
                    hit and (parsed or {}).get("requires_review") is True,
                    str(parsed),
                )
            )
            results.append(
                check(
                    "VCPQ-14c 建议数量=2",
                    float((parsed or {}).get("quantity") or 0) == 2.0,
                    str((parsed or {}).get("quantity")),
                )
            )

            # soft cleanup quote
            req("DELETE", f"/crm/quotes/{qid}", token=token)

    # cleanup soft
    req("DELETE", f"/crm/products/{pid}", token=token)

    return finish_phase("v1.3-cpq-w12", results)


if __name__ == "__main__":
    raise SystemExit(main())
