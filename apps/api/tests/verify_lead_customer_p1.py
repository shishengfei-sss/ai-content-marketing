#!/usr/bin/env python3
"""v0.9 P1 验收：转化去重/建商机 + Hook + 360 过滤 + 评分 + 公海。"""
from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import is_at_expected_head
from tests.verify_crm_helpers import (
    admin_token,
    check,
    ensure_crm_test_users,
    finish_phase,
    lead_body,
    req,
    sales_token,
)


def alembic_head() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def main() -> int:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
    finally:
        db.close()

    admin_tok = admin_token()
    sales_tok = sales_token()
    results: list[bool] = []

    out = alembic_head()
    results.append(check("VP1-0 alembic=058", is_at_expected_head(out), out.strip()))

    # 准备客户（用于去重）
    mobile = f"139{int(uuid.uuid4().hex[:8], 16) % 100000000:08d}"
    company = f"去重公司-{uuid.uuid4().hex[:6]}"
    code, cust = req(
        "POST",
        "/crm/customers",
        token=admin_tok,
        body={"company_name": company, "mobile": mobile, "source": "官网"},
    )
    results.append(check("VP1-pre 客户 201", code == 201, str(code)))
    cust_id = (cust or {}).get("id")

    # VP1-1 转化去重 409
    code, lead1 = req(
        "POST",
        "/crm/leads",
        token=sales_tok,
        body=lead_body(company, mobile=mobile, contact_name="王五", source="官网", lead_score=70),
    )
    results.append(check("VP1-1-1 线索 201", code == 201, str(code)))
    lead1_id = (lead1 or {}).get("id")
    code, err = req(
        "POST",
        f"/crm/leads/{lead1_id}/convert",
        token=sales_tok,
        body={"force_create": False},
    )
    results.append(check("VP1-1-2 去重 409", code == 409, f"{code} {err}"))

    # merge
    code, merged = req(
        "POST",
        f"/crm/leads/{lead1_id}/convert",
        token=sales_tok,
        body={"force_create": False, "merge_into_customer_id": cust_id},
    )
    results.append(check("VP1-1-3 合并转化 201", code == 201, f"{code} {merged}"))
    results.append(check("VP1-1-4 merged", bool((merged or {}).get("merged")), str(merged)))
    results.append(
        check("VP1-1-5 客户ID", (merged or {}).get("customer_id") == cust_id, str(merged))
    )

    # VP1-2 create_deal
    company2 = f"建商机公司-{uuid.uuid4().hex[:6]}"
    mobile2 = f"139{int(uuid.uuid4().hex[:8], 16) % 100000000:08d}"
    code, lead2 = req(
        "POST",
        "/crm/leads",
        token=sales_tok,
        body=lead_body(company2, mobile=mobile2, contact_name="赵六", source="Webhook", lead_score=88),
    )
    lead2_id = (lead2 or {}).get("id")
    code, conv2 = req(
        "POST",
        f"/crm/leads/{lead2_id}/convert",
        token=sales_tok,
        body={"force_create": True, "create_deal": True, "deal_amount": 12000},
    )
    results.append(check("VP1-2-1 转化+商机 201", code == 201, f"{code} {conv2}"))
    deal_id = (conv2 or {}).get("deal_id")
    results.append(check("VP1-2-2 deal_id", bool(deal_id), str(conv2)))
    code, deal = req("GET", f"/crm/deals/{deal_id}", token=sales_tok)
    results.append(check("VP1-2-3 商机详情", code == 200 and (deal or {}).get("amount") == 12000, str(deal)))

    # VP1-3 赢单 Hook
    cust2_id = (conv2 or {}).get("customer_id")
    code, cust_before = req("GET", f"/crm/customers/{cust2_id}", token=sales_tok)
    rev0 = float((cust_before or {}).get("total_revenue") or 0)
    code, closed = req(
        "POST",
        f"/crm/deals/{deal_id}/close",
        token=sales_tok,
        body={"status": "won", "amount": 12000},
    )
    results.append(check("VP1-3-1 赢单 200", code == 200, f"{code} {closed}"))
    code, cust_after = req("GET", f"/crm/customers/{cust2_id}", token=sales_tok)
    rev1 = float((cust_after or {}).get("total_revenue") or 0)
    results.append(check("VP1-3-2 revenue+=amount", rev1 == rev0 + 12000, f"{rev0}->{rev1}"))
    results.append(check("VP1-3-3 last_deal_date", bool((cust_after or {}).get("last_deal_date")), str(cust_after)))
    code, again = req(
        "POST",
        f"/crm/deals/{deal_id}/close",
        token=sales_tok,
        body={"status": "won", "amount": 12000},
    )
    results.append(check("VP1-3-4 重复关闭 409", code == 409, str(code)))

    # VP1-4 阶段 → Activity
    code, pipes = req("GET", "/crm/pipelines", token=admin_tok)
    items = (pipes or {}).get("items") if isinstance(pipes, dict) else pipes
    pipe = (items or [None])[0] if items else None
    pipe_id = (pipe or {}).get("id")
    stages = (pipe or {}).get("stages") or []
    stage0 = stages[0]["id"] if stages else None
    stage1 = stages[1]["id"] if len(stages) > 1 else stage0
    code, deal_b = req(
        "POST",
        "/crm/deals",
        token=sales_tok,
        body={
            "title": f"阶段推进-{uuid.uuid4().hex[:4]}",
            "customer_id": cust_id,
            "amount": 100,
            "pipeline_id": pipe_id,
            "stage_id": stage0,
            "source": "官网",
        },
    )
    deal_b_id = (deal_b or {}).get("id")
    code, stage_resp = req(
        "POST",
        f"/crm/deals/{deal_b_id}/stage",
        token=sales_tok,
        body={"stage_id": stage1, "note": "推进"},
    )
    results.append(check("VP1-4-1 换阶段 200", code == 200, f"{code} {stage_resp}"))
    code, acts = req("GET", f"/crm/activities?customer_id={cust_id}", token=sales_tok)
    act_list = acts if isinstance(acts, list) else (acts or {}).get("items") or []
    contents = [a.get("content", "") for a in act_list]
    results.append(
        check(
            "VP1-4-2 含推进 Activity",
            any("推进到" in c for c in contents),
            str(contents[:5]),
        )
    )

    # VP1-5 评分引擎
    company_s = f"评分公司-{uuid.uuid4().hex[:6]}"
    mobile_s = f"139{int(uuid.uuid4().hex[:8], 16) % 100000000:08d}"
    code, lead_s = req(
        "POST",
        "/crm/leads",
        token=sales_tok,
        body=lead_body(company_s, mobile=mobile_s, contact_name="评分人", source="其他", lead_score=0),
    )
    lead_s_id = (lead_s or {}).get("id")
    code, rule = req(
        "POST",
        "/crm/lead-scoring/rules",
        token=admin_tok,
        body={
            "name": f"规则-{uuid.uuid4().hex[:4]}",
            "condition_json": {"field": "company_name", "operator": "contains", "value": company_s},
            "score_value": 15,
            "priority": 1,
            "is_active": True,
        },
    )
    results.append(check("VP1-5-1 建规则 201", code == 201, f"{code} {rule}"))
    code, scored = req("POST", f"/crm/leads/{lead_s_id}/recalculate-score", token=sales_tok)
    results.append(check("VP1-5-2 重算 200", code == 200, f"{code} {scored}"))
    results.append(
        check("VP1-5-3 lead_score==15", (scored or {}).get("lead_score") == 15, str(scored))
    )

    # VP1-6 公海认领/回收
    code, pool = req(
        "POST",
        "/crm/lead-pools",
        token=admin_tok,
        body={"name": f"默认公海-{uuid.uuid4().hex[:4]}", "auto_reclaim_days": 30},
    )
    results.append(check("VP1-6-1 建公海 201", code == 201, f"{code} {pool}"))
    pool_id = (pool or {}).get("id")
    company_p = f"公海公司-{uuid.uuid4().hex[:6]}"
    mobile_p = f"139{int(uuid.uuid4().hex[:8], 16) % 100000000:08d}"
    code, lead_p = req(
        "POST",
        "/crm/leads",
        token=sales_tok,
        body=lead_body(company_p, mobile=mobile_p, contact_name="公海人", source="线下"),
    )
    lead_p_id = (lead_p or {}).get("id")
    code, reclaimed = req(
        "POST",
        f"/crm/leads/{lead_p_id}/reclaim-to-pool",
        token=sales_tok,
        body={"pool_id": pool_id},
    )
    results.append(check("VP1-6-2 回收 200", code == 200, f"{code} {reclaimed}"))
    results.append(
        check(
            "VP1-6-3 owner=null",
            (reclaimed or {}).get("owner_user_id") is None and (reclaimed or {}).get("pool_id") == pool_id,
            str(reclaimed),
        )
    )
    code, claimed = req(
        "POST",
        f"/crm/lead-pools/{pool_id}/claim",
        token=sales_tok,
        body={"lead_id": lead_p_id},
    )
    results.append(check("VP1-6-4 认领 200", code == 200, f"{code} {claimed}"))
    results.append(
        check(
            "VP1-6-5 认领后有 owner",
            bool((claimed or {}).get("owner_user_id")) and bool((claimed or {}).get("claimed_at")),
            str(claimed),
        )
    )

    # VP1-7 360 过滤
    code, quotes = req("GET", f"/crm/quotes?customer_id={cust_id}", token=admin_tok)
    results.append(check("VP1-7-1 quotes by customer 200", code == 200, str(code)))
    code, contracts = req("GET", f"/crm/contracts?customer_id={cust_id}", token=admin_tok)
    results.append(check("VP1-7-2 contracts by customer 200", code == 200, str(code)))
    code, orders = req("GET", f"/crm/orders?customer_id={cust_id}", token=admin_tok)
    results.append(check("VP1-7-3 orders by customer 200", code == 200, str(code)))
    code, pays = req("GET", f"/crm/payments?customer_id={cust_id}", token=admin_tok)
    results.append(check("VP1-7-4 payments by customer 200", code == 200, str(code)))

    return finish_phase("v0.9 lead/customer P1", results)


if __name__ == "__main__":
    raise SystemExit(main())
