#!/usr/bin/env python3
"""CRM-2 Phase B-1 验收：deal_service CRUD + 阶段推进 + 关闭 + 转订单 + 阶段日志。

详见 docs/v0.7-crm-deal执行计划.md §Phase B。
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
    ensure_crm_test_users,
    finish_phase,
    lead_body,
    req,
    run_step_parser,
    sales_token,
)


def _ensure_customer(admin_tok: str) -> str:
    """admin 创建一个客户并返回 id（用于商机 customer_id）。"""
    code, cust = req(
        "POST",
        "/crm/customers",
        token=admin_tok,
        body={
            "company_name": f"商机测试客户-{uuid.uuid4().hex[:6]}",
            "mobile": f"139{uuid.uuid4().hex[:8]}"[:11],
        },
    )
    assert code == 201, cust
    return cust["id"]


def step_b1_1(results: list[bool]) -> None:
    """商机 CRUD + 阶段推进 + 关闭 + 转订单。"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
    finally:
        db.close()

    admin_tok = admin_token()
    sales_tok = sales_token()

    # 1. 取默认管道（应已由 036 种子）
    code, pipes = req("GET", "/crm/pipelines", token=sales_tok)
    results.append(check("VB1-1-1 GET pipelines 200", code == 200, str(code)))
    if code != 200 or not pipes:
        results.append(check("VB1-1-2 默认管道存在", False, str(pipes)))
        return
    default_pipe = next((p for p in pipes if p["is_default"]), pipes[0])
    stages = default_pipe["stages"]
    results.append(check("VB1-1-2 默认管道有阶段", len(stages) >= 2, str(len(stages))))
    first_stage_id = stages[0]["id"]
    won_stage = next((s for s in stages if s["is_won_stage"]), None)
    lost_stage = next((s for s in stages if s["is_lost_stage"]), None)
    results.append(check("VB1-1-3 含赢单阶段", won_stage is not None, ""))
    results.append(check("VB1-1-4 含输单阶段", lost_stage is not None, ""))

    # 2. 创建客户
    customer_id = _ensure_customer(admin_tok)

    # 3. sales 创建商机（缺省管道/阶段）
    code, deal = req(
        "POST",
        "/crm/deals",
        token=sales_tok,
        body={
            "title": f"测试商机-{uuid.uuid4().hex[:6]}",
            "customer_id": customer_id,
            "amount": 10000,
        },
    )
    results.append(check("VB1-1-5 sales创建商机 201", code == 201, str(code)))
    if code != 201:
        return
    deal_id = deal["id"]
    results.append(check("VB1-1-6 默认管道/阶段", deal["pipeline_id"] == default_pipe["id"], ""))
    results.append(check("VB1-1-7 默认状态 open", deal["status"] == "open", deal["status"]))
    results.append(
        check(
            "VB1-1-8 默认概率=第一阶段",
            deal["probability"] == stages[0]["probability"],
            f"{deal['probability']} vs {stages[0]['probability']}",
        )
    )

    # 4. 推进阶段（第二阶段）
    second_stage_id = stages[1]["id"]
    code, deal2 = req(
        "POST",
        f"/crm/deals/{deal_id}/stage",
        token=sales_tok,
        body={"stage_id": second_stage_id, "note": "推进到第二阶段"},
    )
    results.append(check("VB1-1-9 推进阶段 200", code == 200, str(code)))
    results.append(
        check(
            "VB1-1-10 概率更新",
            deal2["probability"] == stages[1]["probability"],
            f"{deal2['probability']} vs {stages[1]['probability']}",
        )
    )

    # 5. 阶段日志
    code, logs = req("GET", f"/crm/deals/{deal_id}/stage-logs", token=sales_tok)
    results.append(check("VB1-1-11 阶段日志 200", code == 200, str(code)))
    results.append(check("VB1-1-12 至少2条日志", len(logs) >= 2, str(len(logs))))

    # 6. 关闭赢单
    code, deal3 = req(
        "POST",
        f"/crm/deals/{deal_id}/close",
        token=sales_tok,
        body={"status": "won", "amount": 12000},
    )
    results.append(check("VB1-1-13 赢单 200", code == 200, str(code)))
    results.append(check("VB1-1-14 状态 won", deal3["status"] == "won", deal3["status"]))
    results.append(check("VB1-1-15 金额更新", deal3["amount"] == 12000, str(deal3["amount"])))
    results.append(check("VB1-1-16 closed_at 落库", deal3["closed_at"] is not None, ""))

    # 7. 重复关闭 → 409
    code, _ = req("POST", f"/crm/deals/{deal_id}/close", token=sales_tok, body={"status": "lost"})
    results.append(check("VB1-1-17 重复关闭 409", code == 409, str(code)))

    # 8. 输单必填 loss_reason
    customer_id2 = _ensure_customer(admin_tok)
    code, deal4 = req(
        "POST",
        "/crm/deals",
        token=sales_tok,
        body={"title": "输单测试", "customer_id": customer_id2, "amount": 5000},
    )
    deal4_id = deal4["id"]
    code, _ = req("POST", f"/crm/deals/{deal4_id}/close", token=sales_tok, body={"status": "lost"})
    results.append(check("VB1-1-18 输单必填loss_reason 400", code == 400, str(code)))
    code, deal4b = req(
        "POST",
        f"/crm/deals/{deal4_id}/close",
        token=sales_tok,
        body={"status": "lost", "loss_reason": "价格太高"},
    )
    results.append(check("VB1-1-19 输单成功", code == 200 and deal4b["status"] == "lost", str(code)))


def step_b1_2(results: list[bool]) -> None:
    """商机转订单（最短路径）。"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
    finally:
        db.close()

    admin_tok = admin_token()
    sales_tok = sales_token()
    customer_id = _ensure_customer(admin_tok)

    code, deal = req(
        "POST",
        "/crm/deals",
        token=sales_tok,
        body={"title": f"转单测试-{uuid.uuid4().hex[:6]}", "customer_id": customer_id, "amount": 8000},
    )
    assert code == 201, deal
    deal_id = deal["id"]

    code, out = req("POST", f"/crm/deals/{deal_id}/convert-to-order", token=sales_tok)
    results.append(check("VB1-2-1 商机转订单 201", code == 201, str(code)))
    if code != 201:
        return
    order_id = out["order_id"]
    results.append(check("VB1-2-2 返回order_id", order_id is not None, ""))

    # 验证订单字段
    code, order = req("GET", f"/crm/orders/{order_id}", token=sales_tok)
    # 订单路由在 Phase E 完整实现；这里仅校验 deal.converted_order_id 标记
    # 如果订单路由未实现，回退到 DB 直查
    if code == 404:
        from app.database import SessionLocal as _SL
        from app.models.crm import Deal as _Deal

        db2 = _SL()
        try:
            d = db2.query(_Deal).filter(_Deal.id == uuid.UUID(deal_id)).first()
            results.append(
                check(
                    "VB1-2-3 deal.converted_order_id 标记",
                    d is not None and str(d.converted_order_id) == order_id,
                    str(d.converted_order_id) if d else "no deal",
                )
            )
        finally:
            db2.close()
    else:
        results.append(check("VB1-2-3 GET order 200/404", code in (200, 404), str(code)))


STEPS = {
    "B1-1": step_b1_1,
    "B1-2": step_b1_2,
}


def main() -> int:
    args = run_step_parser(list(STEPS.keys()))
    results: list[bool] = []
    if args.step:
        STEPS[args.step](results)
    else:
        for fn in STEPS.values():
            fn(results)
    return finish_phase("2 B1", results)


if __name__ == "__main__":
    raise SystemExit(main())
