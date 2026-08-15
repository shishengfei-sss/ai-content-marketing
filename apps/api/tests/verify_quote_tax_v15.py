#!/usr/bin/env python3
"""v1.5 产品与报价价税增强 — 自动化验收。

用法：
  python tests/verify_quote_tax_v15.py              # 默认 unit：价税引擎纯函数
  python tests/verify_quote_tax_v15.py --mode unit
  python tests/verify_quote_tax_v15.py --mode impl  # API 全量（需 Alembic 087+ 与前后端落地）
  python tests/verify_quote_tax_v15.py --mode doc  # 文档门禁

退出码：0 全绿，1 有失败。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from decimal import Decimal
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = API_ROOT.parent / "web"
REPO_ROOT = API_ROOT.parent.parent
sys.path.insert(0, str(API_ROOT))

from app.services.crm.tax_engine import (  # noqa: E402
    TaxLineIn,
    compute_tax_lines,
    money,
    split_untaxed_unit_price,
)
from tests.http_client import check  # noqa: E402
from tests.verify_crm_helpers import finish_phase  # noqa: E402


def _docs_ok() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    prd = REPO_ROOT / "产品报价价税-prd" / "产品报价价税-prd.html"
    ux = REPO_ROOT / "产品报价价税UI交互" / "产品报价价税UI交互.html"
    plan = REPO_ROOT / "docs" / "v1.5-产品报价价税增强执行计划.md"
    srs = REPO_ROOT / "docs" / "需求规格.md"
    results.append(check("V15-DOC-01 PRD exists", prd.is_file(), str(prd)))
    results.append(check("V15-DOC-02 UI/UX exists", ux.is_file(), str(ux)))
    results.append(check("V15-DOC-03 exec plan exists", plan.is_file(), str(plan)))
    text = srs.read_text(encoding="utf-8") if srs.is_file() else ""
    results.append(check("V15-DOC-04 SRS §3.26", "3.26" in text and "FR-QUOTE-TAX" in text, "§3.26"))
    prd_t = prd.read_text(encoding="utf-8") if prd.is_file() else ""
    results.append(check("V15-DOC-05 PRD 尾差 P0", "尾差" in prd_t and "0.01" in prd_t, "tail"))
    return results


def _unit_engine() -> list[tuple[str, bool, str]]:
    """纯函数验收：与执行计划 V15-U* 对齐。"""
    results: list[tuple[str, bool, str]] = []

    # U01 单行基础
    r = compute_tax_lines([TaxLineIn(unit_price=100, quantity=2, tax_rate=13)])
    results.append(check("V15-U01 line_total", r.lines[0].line_total == money(200), str(r.lines[0].line_total)))
    results.append(check("V15-U01 tax", r.lines[0].tax_amount == money(26), str(r.lines[0].tax_amount)))
    results.append(check("V15-U01 incl", r.lines[0].line_incl_tax == money(226), str(r.lines[0].line_incl_tax)))
    results.append(
        check(
            "V15-U01 balance",
            r.total_ex_tax + r.tax_total == r.amount_incl_tax,
            f"{r.total_ex_tax}+{r.tax_total}!={r.amount_incl_tax}",
        )
    )

    # U02 行折扣
    r = compute_tax_lines([TaxLineIn(unit_price=100, quantity=1, discount_rate=10, tax_rate=13)])
    # 90 * 0.13 = 11.7
    results.append(check("V15-U02 line after disc", r.lines[0].line_total == money(90), str(r.lines[0].line_total)))
    results.append(check("V15-U02 tax", r.lines[0].tax_amount == money("11.70"), str(r.lines[0].tax_amount)))

    # U03 多行求和
    r = compute_tax_lines(
        [
            TaxLineIn(unit_price=100, quantity=1, tax_rate=13),
            TaxLineIn(unit_price=50, quantity=2, tax_rate=6),
        ]
    )
    results.append(check("V15-U03 total_ex", r.total_ex_tax == money(200), str(r.total_ex_tax)))
    # 13 + 6 = 19
    results.append(check("V15-U03 tax_total", r.tax_total == money(19), str(r.tax_total)))
    results.append(check("V15-U03 incl", r.amount_incl_tax == money(219), str(r.amount_incl_tax)))

    # U04 含税拆未税
    up = split_untaxed_unit_price(113, 13, price_includes_tax=True)
    results.append(check("V15-U04 split", up == money(100), str(up)))
    up2 = split_untaxed_unit_price(100, 13, price_includes_tax=False)
    results.append(check("V15-U04 no-split", up2 == money(100), str(up2)))

    # U05 头折摊入后再税
    r = compute_tax_lines(
        [
            TaxLineIn(unit_price=100, quantity=1, tax_rate=13),
            TaxLineIn(unit_price=100, quantity=1, tax_rate=13),
        ],
        header_discount_rate=10,
    )
    # 各行未税 90，税 11.70；合计未税 180，税 23.40
    results.append(check("V15-U05 header total_ex", r.total_ex_tax == money(180), str(r.total_ex_tax)))
    results.append(check("V15-U05 line0", r.lines[0].line_total == money(90), str(r.lines[0].line_total)))
    results.append(
        check(
            "V15-U05 balance",
            r.total_ex_tax + r.tax_total == r.amount_incl_tax,
            f"{r.total_ex_tax} {r.tax_total} {r.amount_incl_tax}",
        )
    )

    # U06 尾差 ±0.01：构造「每行 round 之和 ≠ exact」
    # 经典：三行未税 0.33 / 0.33 / 0.34，税率 13%
    # 行税：0.04, 0.04, 0.04 = 0.12；exact = round(1.00*0.13,2)=0.13 → delta +0.01
    r = compute_tax_lines(
        [
            TaxLineIn(unit_price="0.33", quantity=1, tax_rate=13),
            TaxLineIn(unit_price="0.33", quantity=1, tax_rate=13),
            TaxLineIn(unit_price="0.34", quantity=1, tax_rate=13),
        ]
    )
    results.append(check("V15-U06 total_ex=1", r.total_ex_tax == money(1), str(r.total_ex_tax)))
    results.append(check("V15-U06 exact=0.13", r.exact_tax == money("0.13"), str(r.exact_tax)))
    results.append(check("V15-U06 tax_total=0.13", r.tax_total == money("0.13"), str(r.tax_total)))
    results.append(check("V15-U06 tail applied", abs(r.tail_delta) == money("0.01"), str(r.tail_delta)))
    results.append(
        check(
            "V15-U06 last line absorbs",
            r.lines[-1].tax_amount == money("0.05"),
            str([o.tax_amount for o in r.lines]),
        )
    )
    results.append(
        check(
            "V15-U06 balance after tail",
            r.total_ex_tax + r.tax_total == r.amount_incl_tax,
            f"{r.total_ex_tax}+{r.tax_total}!={r.amount_incl_tax}",
        )
    )

    # U07 税率空
    r = compute_tax_lines([TaxLineIn(unit_price=100, quantity=1, tax_rate=None)])
    results.append(check("V15-U07 tax0", r.tax_total == money(0), str(r.tax_total)))
    results.append(check("V15-U07 incl=ex", r.amount_incl_tax == r.total_ex_tax, str(r.amount_incl_tax)))

    # U08 头折分摊末行未税找平（奇数金额）
    r = compute_tax_lines(
        [
            TaxLineIn(unit_price=100, quantity=1, tax_rate=0),
            TaxLineIn(unit_price=50, quantity=1, tax_rate=0),
        ],
        header_discount_rate=10,
    )
    # subtotal 150 → target 135；第一行 round(100/150*135)=90，第二行 45
    results.append(check("V15-U08 sum135", r.total_ex_tax == money(135), str(r.total_ex_tax)))
    results.append(check("V15-U08 parts", r.lines[0].line_total + r.lines[1].line_total == money(135), str(r.lines)))

    return results


def _static_web() -> list[tuple[str, bool, str]]:
    """前端静态门禁（实现后应变绿；unit 模式仅检查引擎文件存在）。"""
    results: list[tuple[str, bool, str]] = []
    engine = API_ROOT / "app" / "services" / "crm" / "tax_engine.py"
    results.append(check("V15-S01 tax_engine.py", engine.is_file(), str(engine)))
    return results


def _impl_api() -> list[tuple[str, bool, str]]:
    """API 全量：依赖迁移 087 + Product/Quote/Order 接线。"""
    from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
    from tests.verify_crm_helpers import admin_token, ensure_crm_test_users, req
    from app.database import SessionLocal

    results: list[tuple[str, bool, str]] = []

    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    # 实现阶段 EXPECTED_HEAD 应升到 087；此处同时接受文档中的目标修订号
    head_ok = is_at_expected_head(out) or ("087" in out and "head" in out.lower())
    results.append(check(f"V15-I00 alembic head ({EXPECTED_HEAD}|087)", head_ok, out.strip()[:200]))

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
    finally:
        db.close()

    tok = admin_token()

    # 产品税字段
    code, prod = req(
        "POST",
        "/crm/products",
        token=tok,
        body={
            "name": f"价税产品-{uuid.uuid4().hex[:6]}",
            "list_price": 113,
            "default_tax_rate": 13,
            "price_includes_tax": True,
            "is_active": True,
        },
    )
    results.append(check("V15-I01 create product 201", code == 201, f"{code} {prod}"))
    results.append(
        check(
            "V15-I02 product tax fields",
            (prod or {}).get("default_tax_rate") in (13, 13.0, "13")
            and bool((prod or {}).get("price_includes_tax")) is True,
            str(prod),
        )
    )

    code, cust = req(
        "POST",
        "/crm/customers",
        token=tok,
        body={"company_name": f"价税客户-{uuid.uuid4().hex[:6]}", "mobile": f"138{uuid.uuid4().hex[:8]}"[:11]},
    )
    results.append(check("V15-I03 customer", code == 201, str(code)))
    cust_id = (cust or {}).get("id")

    # 报价：两行 + 税率，校验平衡与字段
    code, quote = req(
        "POST",
        "/crm/quotes",
        token=tok,
        body={
            "customer_id": cust_id,
            "subject": f"价税报价-{uuid.uuid4().hex[:6]}",
            "discount_rate": 0,
            "lines": [
                {
                    "product_id": (prod or {}).get("id"),
                    "name": (prod or {}).get("name") or "P",
                    "quantity": 1,
                    "unit_price": 100,
                    "discount_rate": 0,
                    "tax_rate": 13,
                    "line_total": 100,
                },
                {
                    "name": "服务行",
                    "quantity": 1,
                    "unit_price": 100,
                    "discount_rate": 0,
                    "tax_rate": 13,
                    "line_total": 100,
                },
            ],
        },
    )
    results.append(check("V15-I04 create quote 201", code == 201, f"{code} {quote}"))
    lines = (quote or {}).get("lines") or []
    tax_total = (quote or {}).get("tax_total")
    if tax_total is None and lines:
        tax_total = sum(float(l.get("tax_amount") or 0) for l in lines)
    total_ex = float((quote or {}).get("total_amount") or 0)
    incl = (quote or {}).get("amount_incl_tax")
    if incl is None:
        incl = total_ex + float(tax_total or 0)
    results.append(
        check(
            "V15-I05 quote balance",
            abs(total_ex + float(tax_total or 0) - float(incl)) < 0.001,
            f"ex={total_ex} tax={tax_total} incl={incl}",
        )
    )
    results.append(
        check(
            "V15-I06 line tax fields",
            all(l.get("tax_rate") is not None for l in lines) and all("tax_amount" in l for l in lines),
            str(lines),
        )
    )

    # 尾差场景：三行 0.33/0.33/0.34 @13%
    code, q2 = req(
        "POST",
        "/crm/quotes",
        token=tok,
        body={
            "customer_id": cust_id,
            "subject": f"尾差报价-{uuid.uuid4().hex[:6]}",
            "lines": [
                {"name": "A", "quantity": 1, "unit_price": 0.33, "tax_rate": 13, "line_total": 0.33},
                {"name": "B", "quantity": 1, "unit_price": 0.33, "tax_rate": 13, "line_total": 0.33},
                {"name": "C", "quantity": 1, "unit_price": 0.34, "tax_rate": 13, "line_total": 0.34},
            ],
        },
    )
    results.append(check("V15-I07 tail quote 201", code == 201, f"{code}"))
    q2_lines = sorted((q2 or {}).get("lines") or [], key=lambda x: x.get("sort_order", 0))
    if q2_lines:
        last_tax = float(q2_lines[-1].get("tax_amount") or 0)
        sum_tax = sum(float(l.get("tax_amount") or 0) for l in q2_lines)
        results.append(check("V15-I08 tail last~0.05", abs(last_tax - 0.05) < 0.001, str(last_tax)))
        results.append(check("V15-I09 tail sum=0.13", abs(sum_tax - 0.13) < 0.001, str(sum_tax)))
    else:
        results.append(check("V15-I08 tail last~0.05", False, "no lines"))
        results.append(check("V15-I09 tail sum=0.13", False, "no lines"))

    qid = (quote or {}).get("id")
    if qid:
        code, _ = req("POST", f"/crm/quotes/{qid}/send", token=tok)
        results.append(check("V15-I09b send before convert", code == 200, f"{code}"))
        code, _ = req("POST", f"/crm/quotes/{qid}/accept", token=tok)
        results.append(check("V15-I09c accept before convert", code == 200, f"{code}"))
        code, conv = req("POST", f"/crm/quotes/{qid}/convert-to-order", token=tok)
        results.append(check("V15-I10 convert 200/201", code in (200, 201), f"{code} {conv}"))
        oid = (conv or {}).get("order_id")
        order = None
        if oid:
            code, order = req("GET", f"/crm/orders/{oid}", token=tok)
            results.append(check("V15-I10b get order", code == 200, str(code)))
        olines = (order or {}).get("lines") or []
        qlines = (quote or {}).get("lines") or []
        if olines and qlines:
            ok = True
            for ql, ol in zip(
                sorted(qlines, key=lambda x: x.get("sort_order", 0)),
                sorted(olines, key=lambda x: x.get("sort_order", 0)),
            ):
                if float(ql.get("tax_rate") or 0) != float(ol.get("tax_rate") or 0):
                    ok = False
                if abs(float(ql.get("tax_amount") or 0) - float(ol.get("tax_amount") or 0)) > 0.001:
                    ok = False
            results.append(check("V15-I11 convert tax copy", ok, f"q={qlines} o={olines}"))
        else:
            results.append(check("V15-I11 convert tax copy", False, f"q={qlines} o={olines}"))
    else:
        results.append(check("V15-I10 convert 200/201", False, "no quote id"))
        results.append(check("V15-I11 convert tax copy", False, "skipped"))

    # 静态 UI 门禁（impl）
    qform = (WEB_ROOT / "src" / "views" / "crm" / "QuoteFormDialog.vue").read_text(encoding="utf-8")
    results.append(check("V15-I12 QuoteForm tax_rate", "tax_rate" in qform, "QuoteFormDialog"))
    products = (WEB_ROOT / "src" / "views" / "crm" / "Products.vue").read_text(encoding="utf-8")
    results.append(
        check(
            "V15-I13 Products default_tax_rate",
            "default_tax_rate" in products or "price_includes_tax" in products,
            "Products.vue",
        )
    )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="v1.5 quote/product tax verify")
    parser.add_argument("--mode", choices=("doc", "unit", "impl"), default="unit")
    args = parser.parse_args()

    if args.mode == "doc":
        return finish_phase("v1.5-quote-tax-DOC", _docs_ok())
    if args.mode == "unit":
        return finish_phase("v1.5-quote-tax-UNIT", _docs_ok() + _static_web() + _unit_engine())
    return finish_phase("v1.5-quote-tax-IMPL", _docs_ok() + _unit_engine() + _impl_api())


if __name__ == "__main__":
    raise SystemExit(main())
