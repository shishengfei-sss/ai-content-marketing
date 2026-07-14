#!/usr/bin/env python3
"""v0.8 商机增强 P2 验收。"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")

from tests.alembic_head import is_at_expected_head
from tests.verify_crm_helpers import admin_token, check, ensure_crm_test_users, finish_phase, req


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

    tok = admin_token()
    results: list[bool] = []

    results.append(check("VP2-0 alembic=047", is_at_expected_head(alembic_head()), alembic_head().strip()))

    code, pipes = req("GET", "/crm/pipelines", token=tok)
    pipe = (pipes or [{}])[0]
    pid, sid = pipe.get("id"), (pipe.get("stages") or [{}])[0].get("id")
    code, cust = req("POST", "/crm/customers", token=tok, body={
        "company_name": f"P2客户-{uuid.uuid4().hex[:6]}",
        "mobile": f"139{uuid.uuid4().hex[:8]}"[:11],
    })
    cust_id = cust.get("id")

    # VP2-01 max_stay_days
    code, stage = req("PATCH", f"/crm/pipelines/{pid}/stages/{sid}", token=tok, body={"max_stay_days": 7})
    results.append(check("VP2-01-1 阶段 max_stay_days 200", code == 200, str(code)))
    results.append(check("VP2-01-2 max_stay_days=7", (stage or {}).get("max_stay_days") == 7, str((stage or {}).get("max_stay_days"))))

    code, deal = req("POST", "/crm/deals", token=tok, body={
        "title": f"P2商机-{uuid.uuid4().hex[:6]}",
        "customer_id": cust_id, "pipeline_id": pid, "stage_id": sid, "amount": 1000,
    })
    deal_id = deal.get("id")
    results.append(check("VP2-pre 创建商机", code == 201, str(code)))

    code, det = req("GET", f"/crm/deals/{deal_id}", token=tok)
    results.append(check("VP2-01-3 详情含 stage_stay_days", "stage_stay_days" in (det or {}), str(det)))

    # VP2-02 收入预测
    code, fc = req("GET", f"/analytics/deal-forecast?pipeline_id={pid}", token=tok)
    results.append(check("VP2-02-1 预测 200", code == 200, str(code)))
    results.append(check("VP2-02-2 含 weighted_amount", "weighted_amount" in (fc or {}), str(fc)))

    # VP2-03 赢输分析 - 先关闭一笔输单
    code, _ = req("POST", f"/crm/deals/{deal_id}/close", token=tok, body={
        "status": "lost", "loss_reason": "价格过高", "reason": "价格过高", "competitor": "竞品X",
    })
    results.append(check("VP2-03-1 关闭输单 200", code == 200, str(code)))
    code, wl = req("GET", "/analytics/deal-win-loss", token=tok)
    results.append(check("VP2-03-2 赢输报表 200", code == 200, str(code)))
    results.append(check("VP2-03-3 含 by_reason", "by_reason" in (wl or {}), str(wl)))

    # 再建一笔用于克隆/批量
    code, deal2 = req("POST", "/crm/deals", token=tok, body={
        "title": f"P2批量-{uuid.uuid4().hex[:6]}",
        "customer_id": cust_id, "pipeline_id": pid, "stage_id": sid, "amount": 500,
    })
    deal2_id = deal2.get("id")

    # VP2-07 克隆
    code, cloned = req("POST", f"/crm/deals/{deal2_id}/clone", token=tok)
    results.append(check("VP2-07-1 克隆 201", code == 201, str(code)))
    results.append(check("VP2-07-2 新商机ID不同", (cloned or {}).get("deal_id") != deal2_id, str(cloned)))

    # VP2-05 批量更新
    code, deal3 = req("POST", "/crm/deals", token=tok, body={
        "title": f"P2批量2-{uuid.uuid4().hex[:6]}",
        "customer_id": cust_id, "pipeline_id": pid, "stage_id": sid, "amount": 300,
    })
    deal3_id = deal3.get("id")
    stages = pipe.get("stages") or []
    sid2 = stages[1].get("id") if len(stages) > 1 else sid
    code, bat = req("POST", "/crm/deals/batch-update", token=tok, body={
        "deal_ids": [deal2_id, deal3_id], "stage_id": sid2,
    })
    results.append(check("VP2-05-1 批量更新 200", code == 200, str(code)))
    results.append(check("VP2-05-2 updated>=1", (bat or {}).get("updated", 0) >= 1, str(bat)))

    # 清理
    for did in [deal2_id, deal3_id, (cloned or {}).get("deal_id")]:
        if did:
            req("DELETE", f"/crm/deals/{did}", token=tok)
    req("PATCH", f"/crm/pipelines/{pid}/stages/{sid}", token=tok, body={"max_stay_days": None})

    return finish_phase("v0.8-deal-P2", results)


if __name__ == "__main__":
    sys.exit(main())
