#!/usr/bin/env python3
"""v0.8 商机增强 P1 验收：跟进记录 + 附件 + 明细行 + 报价桥接 + 漏斗报表 + 团队协作。"""
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
from tests.verify_crm_helpers import (
    admin_token,
    check,
    ensure_crm_test_users,
    finish_phase,
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

    # VP1-0 迁移 head = 045
    out = alembic_head()
    results.append(check("VP1-0 alembic=045", is_at_expected_head(out), out.strip()))

    # 准备：管道 / 阶段 / 客户
    code, pipes = req("GET", "/crm/pipelines", token=admin_tok)
    pipe = (pipes or [{}])[0]
    pipe_id = pipe.get("id")
    stage_id = (pipe.get("stages") or [{}])[0].get("id")
    code, cust = req("POST", "/crm/customers", token=admin_tok, body={
        "company_name": f"P1客户-{uuid.uuid4().hex[:6]}",
        "mobile": f"139{uuid.uuid4().hex[:8]}"[:11],
    })
    cust_id = cust.get("id")
    results.append(check("VP1-pre 准备管道/客户", bool(pipe_id and stage_id and cust_id), f"{pipe_id}/{cust_id}"))

    # 准备一个带明细的商机
    code, deal = req("POST", "/crm/deals", token=admin_tok, body={
        "title": f"P1商机-{uuid.uuid4().hex[:6]}",
        "customer_id": cust_id,
        "pipeline_id": pipe_id,
        "stage_id": stage_id,
        "amount": 0,
        "lines": [
            {"product_name": "产品A", "unit": "套", "quantity": 2, "unit_price": 100, "discount_percent": 10, "subtotal": 180},
            {"product_name": "产品B", "unit": "个", "quantity": 1, "unit_price": 50, "discount_percent": 0, "subtotal": 50},
        ],
    })
    deal_id = deal.get("id")
    results.append(check("VP1-pre 创建带明细商机 201", code == 201, str(code)))

    # ===== P1-03 明细行 =====
    results.append(check("VP1-03-1 明细行写入", len((deal or {}).get("lines") or []) == 2, str(len((deal or {}).get("lines") or []))))
    results.append(check("VP1-03-2 amount 汇总=230", (deal or {}).get("amount") == 230.0, str((deal or {}).get("amount"))))
    code, upd = req("PATCH", f"/crm/deals/{deal_id}", token=admin_tok, body={
        "lines": [{"product_name": "产品C", "unit": "件", "quantity": 1, "unit_price": 200, "discount_percent": 0, "subtotal": 200}],
    })
    results.append(check("VP1-03-3 更新明细后重算=200", (upd or {}).get("amount") == 200.0, str((upd or {}).get("amount"))))
    results.append(check("VP1-03-4 更新后明细数=1", len((upd or {}).get("lines") or []) == 1, str(len((upd or {}).get("lines") or []))))

    # ===== P1-01 跟进记录 =====
    code, act = req("POST", f"/crm/deals/{deal_id}/activities", token=admin_tok, body={
        "activity_type": "call", "subject": "首次电话", "content": "沟通需求并约定演示",
    })
    results.append(check("VP1-01-1 创建跟进 201", code == 201, str(code)))
    results.append(check("VP1-01-2 跟进 deal_id 回写", (act or {}).get("deal_id") == deal_id, str((act or {}).get("deal_id"))))
    act_id = (act or {}).get("id")
    code, lst = req("GET", f"/crm/deals/{deal_id}/activities", token=admin_tok)
    results.append(check("VP1-01-3 跟进列表 200 含1条", code == 200 and len(lst) == 1, str(code)))
    code, pa = req("PATCH", f"/crm/activities/{act_id}", token=admin_tok, body={"content": "更新后的跟进内容"})
    results.append(check("VP1-01-4 编辑跟进 200", code == 200 and (pa or {}).get("content") == "更新后的跟进内容", str(code)))
    code, _ = req("DELETE", f"/crm/activities/{act_id}", token=admin_tok)
    results.append(check("VP1-01-5 删除跟进 204", code == 204, str(code)))

    # ===== P1-04 报价桥接 =====
    code, quote = req("POST", f"/crm/deals/{deal_id}/generate-quote", token=admin_tok)
    results.append(check("VP1-04-1 生成报价 201", code == 201, str(code)))
    results.append(check("VP1-04-2 报价 deal_id 回写", (quote or {}).get("deal_id") == deal_id, str((quote or {}).get("deal_id"))))
    results.append(check("VP1-04-3 报价明细=1", len((quote or {}).get("lines") or []) == 1, str(len((quote or {}).get("lines") or []))))
    results.append(check("VP1-04-4 报价金额=200", (quote or {}).get("total_amount") == 200.0, str((quote or {}).get("total_amount"))))
    quote_id = (quote or {}).get("id")

    # ===== P1-05 漏斗报表 =====
    code, funnel = req("GET", f"/analytics/deal-funnel?pipeline_id={pipe_id}", token=admin_tok)
    results.append(check("VP1-05-1 漏斗 200", code == 200, str(code)))
    results.append(check("VP1-05-2 漏斗阶段>0", len(funnel or []) > 0, str(len(funnel or []))))
    first_stage = (funnel or [{}])[0]
    results.append(check("VP1-05-3 首阶段含 conversion_rate", "conversion_rate" in first_stage, str(first_stage.get("conversion_rate"))))

    # ===== P1-06 团队协作 =====
    code, team = req("GET", f"/crm/deals/{deal_id}/team", token=admin_tok)
    results.append(check("VP1-06-1 团队列表 200 含owner", code == 200 and any(m["role"] == "owner" for m in (team or [])), str(code)))
    # sales 加入团队
    code, prof = req("GET", "/auth/me", token=sales_tok)
    sales_uid = (prof or {}).get("user_id") or (prof or {}).get("id")
    code, m = req("POST", f"/crm/deals/{deal_id}/team", token=admin_tok, body={"user_id": sales_uid, "role": "售前"})
    results.append(check("VP1-06-2 添加成员 201", code == 201, str(code)))
    mid = (m or {}).get("id")
    # sales 现在能查看（团队成员身份）
    code, _ = req("GET", f"/crm/deals/{deal_id}", token=sales_tok)
    results.append(check("VP1-06-3 sales 以团队成员查看 200", code == 200, str(code)))
    code, _ = req("DELETE", f"/crm/deals/{deal_id}/team/{mid}", token=admin_tok)
    results.append(check("VP1-06-4 移除成员 204", code == 204, str(code)))

    # ===== P1-02 附件（TestClient multipart）=====
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    H = {"Authorization": f"Bearer {admin_tok}"}
    r = client.post(
        "/api/v1/crm/attachments",
        headers=H,
        params={"entity_type": "deal", "entity_id": deal_id},
        files={"file": ("p1verify.txt", b"p1 attachment content", "text/plain")},
    )
    results.append(check("VP1-02-1 上传附件 201", r.status_code == 201, str(r.status_code)))
    aid = r.json().get("id")
    r = client.get("/api/v1/crm/attachments", headers=H, params={"entity_type": "deal", "entity_id": deal_id})
    results.append(check("VP1-02-2 附件列表 200 含1", r.status_code == 200 and len(r.json()) == 1, str(r.status_code)))
    r = client.get(f"/api/v1/crm/attachments/{aid}/download", headers=H)
    results.append(check("VP1-02-3 下载 200 内容一致", r.status_code == 200 and r.content == b"p1 attachment content", str(r.status_code)))
    r = client.delete(f"/api/v1/crm/attachments/{aid}", headers=H)
    results.append(check("VP1-02-4 删除附件 204", r.status_code == 204, str(r.status_code)))

    # 清理
    if quote_id:
        req("DELETE", f"/crm/quotes/{quote_id}", token=admin_tok)
    req("DELETE", f"/crm/deals/{deal_id}", token=admin_tok)

    return finish_phase("v0.8-deal-P1", results)


if __name__ == "__main__":
    sys.exit(main())
