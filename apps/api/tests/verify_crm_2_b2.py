#!/usr/bin/env python3
"""CRM-2 Phase B-2 验收：pipeline_service CRUD + 在用阶段不可删。"""
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
    req,
    run_step_parser,
    sales_token,
)


def step_b2_1(results: list[bool]) -> None:
    """管道 + 阶段 CRUD + 在用不可删。"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
    finally:
        db.close()

    admin_tok = admin_token()
    sales_tok = sales_token()

    # sales 无 pipeline.manage → 403
    code, _ = req("POST", "/crm/pipelines", token=sales_tok, body={"name": "非法"})
    results.append(check("VB2-1-1 sales创建管道 403", code == 403, str(code)))

    # admin 创建新管道（含 3 阶段）
    pipe_name = f"测试管道-{uuid.uuid4().hex[:6]}"
    code, pipe = req(
        "POST",
        "/crm/pipelines",
        token=admin_tok,
        body={
            "name": pipe_name,
            "is_default": False,
            "stages": [
                {"name": "阶段A", "sort_order": 10, "probability": 10},
                {"name": "阶段B", "sort_order": 20, "probability": 50},
                {"name": "赢单", "sort_order": 90, "probability": 100, "is_won_stage": True},
            ],
        },
    )
    results.append(check("VB2-1-2 admin创建管道 201", code == 201, str(code)))
    if code != 201:
        return
    pipe_id = pipe["id"]
    results.append(check("VB2-1-3 创建含3阶段", len(pipe["stages"]) == 3, str(len(pipe["stages"]))))

    # admin 加阶段
    code, stage = req(
        "POST",
        f"/crm/pipelines/{pipe_id}/stages",
        token=admin_tok,
        body={"name": "阶段C", "sort_order": 30, "probability": 70},
    )
    results.append(check("VB2-1-4 加阶段 201", code == 201, str(code)))
    if code != 201:
        return
    stage_id = stage["id"]

    # admin 改阶段
    code, stage2 = req(
        "PATCH",
        f"/crm/pipelines/{pipe_id}/stages/{stage_id}",
        token=admin_tok,
        body={"probability": 75, "name": "阶段C改"},
    )
    results.append(check("VB2-1-5 改阶段 200", code == 200, str(code)))
    results.append(check("VB2-1-6 概率更新", stage2["probability"] == 75, str(stage2["probability"])))
    results.append(check("VB2-1-7 名字更新", stage2["name"] == "阶段C改", stage2["name"]))

    # 删除空阶段 → 204
    code, _ = req("DELETE", f"/crm/pipelines/{pipe_id}/stages/{stage_id}", token=admin_tok)
    results.append(check("VB2-1-8 删空阶段 204", code == 204, str(code)))

    # 在新管道下创建商机，然后删该阶段 → 409
    # 先建客户
    code, cust = req(
        "POST",
        "/crm/customers",
        token=admin_tok,
        body={"company_name": f"管道测试客户-{uuid.uuid4().hex[:6]}"},
    )
    customer_id = cust["id"]
    # 创建商机到新管道的第一阶段
    first_stage_id = pipe["stages"][0]["id"]
    code, deal = req(
        "POST",
        "/crm/deals",
        token=admin_tok,
        body={
            "title": "占用阶段商机",
            "customer_id": customer_id,
            "pipeline_id": pipe_id,
            "stage_id": first_stage_id,
            "amount": 1000,
        },
    )
    results.append(check("VB2-1-9 创建商机到新管道 201", code == 201, str(code)))
    # 删该阶段 → 409
    code, _ = req("DELETE", f"/crm/pipelines/{pipe_id}/stages/{first_stage_id}", token=admin_tok)
    results.append(check("VB2-1-10 删在用阶段 409", code == 409, str(code)))

    # 删整个管道（有商机）→ 409
    code, _ = req("DELETE", f"/crm/pipelines/{pipe_id}", token=admin_tok)
    results.append(check("VB2-1-11 删有商机的管道 409", code == 409, str(code)))

    # 改管道名
    code, pipe2 = req("PATCH", f"/crm/pipelines/{pipe_id}", token=admin_tok, body={"name": "改名后"})
    results.append(check("VB2-1-12 改管道名 200", code == 200, str(code)))
    results.append(check("VB2-1-13 名字更新", pipe2["name"] == "改名后", pipe2["name"]))


STEPS = {"B2-1": step_b2_1}


def main() -> int:
    args = run_step_parser(list(STEPS.keys()))
    results: list[bool] = []
    if args.step:
        STEPS[args.step](results)
    else:
        for fn in STEPS.values():
            fn(results)
    return finish_phase("2 B2", results)


if __name__ == "__main__":
    raise SystemExit(main())
