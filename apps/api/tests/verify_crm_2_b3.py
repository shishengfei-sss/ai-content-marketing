#!/usr/bin/env python3
"""CRM-2 Phase B-3 验收：权限 + scope（list_own / list_team / list_all）。

- editor 无 deal list 权限 → 403
- marketing 仅 view+create，无 edit → 403
- sales A 创建商机，sales B 仅 list_own → 看不到 A 的商机
- admin list_all → 可见全部
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.verify_crm_helpers import (
    admin_token,
    check,
    editor_token,
    ensure_crm_test_users,
    finish_phase,
    req,
    run_step_parser,
    sales_token,
    SALES_A_PHONE,
    SALES_B_PHONE,
)


def step_b3_1(results: list[bool]) -> None:
    """权限边界。"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
    finally:
        db.close()

    admin_tok = admin_token()
    sales_a = sales_token(SALES_A_PHONE)
    sales_b = sales_token(SALES_B_PHONE)
    editor_tok = editor_token()

    # editor 无 deal list 权限 → 403
    code, _ = req("GET", "/crm/deals", token=editor_tok)
    results.append(check("VB3-1-1 editor list deals 403", code == 403, str(code)))

    # editor 无 deal create → 403
    code, _ = req("POST", "/crm/deals", token=editor_tok, body={"title": "x", "customer_id": str(uuid.uuid4())})
    results.append(check("VB3-1-2 editor create deal 403", code == 403, str(code)))

    # sales A 创建客户 + 商机
    code, cust = req(
        "POST",
        "/crm/customers",
        token=sales_a,
        body={"company_name": f"scope测试-{uuid.uuid4().hex[:6]}"},
    )
    results.append(check("VB3-1-3 sales A 创建客户 201", code == 201, str(code)))
    customer_id = cust["id"]

    code, deal = req(
        "POST",
        "/crm/deals",
        token=sales_a,
        body={"title": f"scope商机-{uuid.uuid4().hex[:6]}", "customer_id": customer_id, "amount": 5000},
    )
    results.append(check("VB3-1-4 sales A 创建商机 201", code == 201, str(code)))
    deal_id = deal["id"]

    # sales B（同租户、list_own）看不到 A 的商机详情 → 403
    code, _ = req("GET", f"/crm/deals/{deal_id}", token=sales_b)
    results.append(check("VB3-1-5 sales B 看不到A商机 403", code == 403, str(code)))

    # sales B list 不含 A 的商机（至少不返回该 deal_id）
    code, lst = req("GET", "/crm/deals", token=sales_b)
    results.append(check("VB3-1-6 sales B list 200", code == 200, str(code)))
    if code == 200:
        ids = {d["id"] for d in lst["items"]}
        results.append(check("VB3-1-7 A商机不在B列表", deal_id not in ids, ""))

    # sales A list 含自己的商机
    code, lst_a = req("GET", "/crm/deals", token=sales_a)
    results.append(check("VB3-1-8 sales A list 200", code == 200, str(code)))
    if code == 200:
        ids_a = {d["id"] for d in lst_a["items"]}
        results.append(check("VB3-1-9 A商机在A列表", deal_id in ids_a, ""))

    # admin list_all 可见该商机
    code, lst_admin = req("GET", "/crm/deals", token=admin_tok)
    results.append(check("VB3-1-10 admin list 200", code == 200, str(code)))
    if code == 200:
        ids_admin = {d["id"] for d in lst_admin["items"]}
        results.append(check("VB3-1-11 A商机在admin列表", deal_id in ids_admin, ""))

    # admin 可看 A 商机详情
    code, _ = req("GET", f"/crm/deals/{deal_id}", token=admin_tok)
    results.append(check("VB3-1-12 admin 看A商机 200", code == 200, str(code)))

    # sales B 试图改 A 的商机 → 403（require_deal 内 assert_can_view_deal）
    code, _ = req("PATCH", f"/crm/deals/{deal_id}", token=sales_b, body={"title": "被B改了"})
    results.append(check("VB3-1-13 sales B 改A商机 403", code == 403, str(code)))


STEPS = {"B3-1": step_b3_1}


def main() -> int:
    args = run_step_parser(list(STEPS.keys()))
    results: list[bool] = []
    if args.step:
        STEPS[args.step](results)
    else:
        for fn in STEPS.values():
            fn(results)
    return finish_phase("2 B3", results)


if __name__ == "__main__":
    raise SystemExit(main())
