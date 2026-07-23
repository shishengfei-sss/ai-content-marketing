#!/usr/bin/env python3
"""关闭态商机分层操作验收：赢单可转单/报价/克隆；输单禁转单；主管可重开。"""
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


def _create_deal(tok: str, *, title: str, customer_id: str, pipeline_id: str, stage_id: str) -> str | None:
    code, deal = req(
        "POST",
        "/crm/deals",
        token=tok,
        body={
            "title": title,
            "customer_id": customer_id,
            "pipeline_id": pipeline_id,
            "stage_id": stage_id,
            "amount": 1000,
            "lines": [
                {
                    "product_name": "测试行",
                    "quantity": 1,
                    "unit_price": 1000,
                    "discount_percent": 0,
                }
            ],
        },
    )
    if code not in (200, 201):
        return None
    return (deal or {}).get("id")


def main() -> int:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
    finally:
        db.close()

    tok = admin_token()
    results: list[bool] = []

    results.append(check("VDC-0 alembic head", is_at_expected_head(alembic_head()), alembic_head().strip()))

    code, pipes = req("GET", "/crm/pipelines", token=tok)
    pipe = (pipes or [{}])[0] if isinstance(pipes, list) else {}
    if not pipe and isinstance(pipes, dict):
        pipe = (pipes.get("items") or [{}])[0]
    pid = pipe.get("id")
    stages = pipe.get("stages") or []
    sid = stages[0].get("id") if stages else None
    results.append(check("VDC-1 管道就绪", bool(pid and sid), str(pipe)[:200]))

    code, cust = req(
        "POST",
        "/crm/customers",
        token=tok,
        body={
            "company_name": f"关闭态客户-{uuid.uuid4().hex[:6]}",
            "mobile": f"138{uuid.uuid4().hex[:8]}"[:11],
        },
    )
    cust_id = (cust or {}).get("id")
    results.append(check("VDC-2 客户", code in (200, 201) and cust_id, f"{code}"))

    won_id = _create_deal(tok, title=f"赢单转单-{uuid.uuid4().hex[:6]}", customer_id=cust_id, pipeline_id=pid, stage_id=sid)
    lost_id = _create_deal(tok, title=f"输单禁转-{uuid.uuid4().hex[:6]}", customer_id=cust_id, pipeline_id=pid, stage_id=sid)
    results.append(check("VDC-3 创建商机", bool(won_id and lost_id), f"won={won_id} lost={lost_id}"))

    code, _ = req("POST", f"/crm/deals/{won_id}/close", token=tok, body={"status": "won", "amount": 1200})
    results.append(check("VDC-4 赢单关闭", code == 200, str(code)))

    code, conv = req("POST", f"/crm/deals/{won_id}/convert-to-order", token=tok)
    results.append(check("VDC-5 赢单可转订单", code in (200, 201) and (conv or {}).get("order_id"), f"{code} {conv}"))

    code, quote = req("POST", f"/crm/deals/{won_id}/generate-quote", token=tok)
    results.append(check("VDC-6 赢单可生成报价", code in (200, 201) and (quote or {}).get("id"), f"{code}"))

    code, cloned = req("POST", f"/crm/deals/{won_id}/clone", token=tok)
    results.append(check("VDC-7 赢单可克隆", code in (200, 201) and (cloned or {}).get("deal_id"), f"{code} {cloned}"))

    code, patched = req("PATCH", f"/crm/deals/{won_id}", token=tok, body={"title": "不该改"})
    results.append(check("VDC-8 赢单不可编辑", code == 409, f"{code} {patched}"))

    code, _ = req("POST", f"/crm/deals/{lost_id}/close", token=tok, body={"status": "lost", "loss_reason": "价格", "reason": "价格"})
    results.append(check("VDC-9 输单关闭", code == 200, str(code)))

    code, blocked = req("POST", f"/crm/deals/{lost_id}/convert-to-order", token=tok)
    results.append(check("VDC-10 输单禁转订单", code == 409, f"{code} {blocked}"))

    code, reopened = req("POST", f"/crm/deals/{lost_id}/reopen", token=tok)
    results.append(
        check(
            "VDC-11 主管可重开",
            code == 200 and (reopened or {}).get("status") == "open",
            f"{code} {reopened}",
        )
    )

    code, again = req("POST", f"/crm/deals/{lost_id}/reopen", token=tok)
    results.append(check("VDC-12 进行中不可再重开", code == 409, f"{code} {again}"))

    return finish_phase("deal_closed_ops", results)


if __name__ == "__main__":
    raise SystemExit(main())
