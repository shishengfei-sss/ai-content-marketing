#!/usr/bin/env python3
"""v0.8 验收：实体自动编号（编号生成 + 规则 CRUD + 唯一性）。"""
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

    # 复位 lead 规则为默认（保证脚本可重复执行：上次 VN-10 改过前缀）
    req("PUT", "/crm/number-rules/lead", token=admin_tok, body={
        "prefix": "XS", "seq_width": 3, "reset_period": "once",
        "date_format": "%Y%m%d", "enabled": True,
    })

    # VN-0 迁移 head = 038
    out = alembic_head()
    results.append(check("VN-0 alembic=038(head)", is_at_expected_head(out), out.strip()))

    # VN-1 GET /crm/number-rules 返回 10 条规则，默认前缀正确
    code, rules = req("GET", "/crm/number-rules", token=sales_tok)
    results.append(check("VN-1-1 GET number-rules 200", code == 200, str(code)))
    rule_map = {r["entity_type"]: r for r in (rules or [])}
    results.append(check("VN-1-2 规则数=10", len(rules or []) == 10, str(len(rules or []))))
    expected_prefix = {
        "lead": "XS", "customer": "KH", "task": "RW", "campaign": "HD",
        "deal": "SJ", "quote": "BJ", "contract": "HT", "order": "DD",
        "payment": "HK", "product": "CP",
    }
    prefix_ok = all(rule_map.get(k, {}).get("prefix") == v for k, v in expected_prefix.items())
    results.append(check("VN-1-3 默认前缀正确", prefix_ok, str({k: rule_map.get(k, {}).get("prefix") for k in expected_prefix})))
    results.append(check("VN-1-4 默认序列宽度=3", all(r.get("seq_width") == 3 for r in rules or []), ""))
    results.append(check("VN-1-5 默认重置周期=once", all(r.get("reset_period") == "once" for r in rules or []), ""))

    # VN-2 创建线索 → lead_number 自动生成
    code, lead = req("POST", "/crm/leads", token=sales_tok, body=lead_body(f"编号测试线索-{uuid.uuid4().hex[:6]}"))
    results.append(check("VN-2-1 创建线索 201", code == 201, str(code)))
    results.append(check("VN-2-2 线索编号生成", bool(lead.get("lead_number")), lead.get("lead_number")))
    results.append(check("VN-2-3 线索编号前缀 XS", (lead.get("lead_number") or "").startswith("XS"), lead.get("lead_number")))

    # VN-3 第二条线索编号递增
    code, lead2 = req("POST", "/crm/leads", token=sales_tok, body=lead_body(f"编号测试线索2-{uuid.uuid4().hex[:6]}"))
    results.append(check("VN-3-1 第二条线索编号递增", lead2.get("lead_number") != lead.get("lead_number"), f"{lead.get('lead_number')} vs {lead2.get('lead_number')}"))

    # VN-4 创建客户 → customer_number
    code, cust = req("POST", "/crm/customers", token=admin_tok, body={
        "company_name": f"编号测试客户-{uuid.uuid4().hex[:6]}",
        "mobile": f"139{uuid.uuid4().hex[:8]}"[:11],
    })
    results.append(check("VN-4-1 创建客户 201", code == 201, str(code)))
    results.append(check("VN-4-2 客户编号 KH", (cust.get("customer_number") or "").startswith("KH"), cust.get("customer_number")))

    # VN-5 创建任务 → task_number
    code, task = req("POST", "/crm/tasks", token=sales_tok, body={"title": f"编号测试任务-{uuid.uuid4().hex[:6]}"})
    results.append(check("VN-5-1 创建任务 201", code == 201, str(code)))
    results.append(check("VN-5-2 任务编号 RW", (task.get("task_number") or "").startswith("RW"), task.get("task_number")))

    # VN-6 创建活动 → campaign_number
    code, camp = req("POST", "/crm/campaigns", token=admin_tok, body={"name": f"编号测试活动-{uuid.uuid4().hex[:6]}"})
    results.append(check("VN-6-1 创建活动 201", code == 201, str(code)))
    results.append(check("VN-6-2 活动编号 HD", (camp.get("campaign_number") or "").startswith("HD"), camp.get("campaign_number")))

    # VN-7 创建商机 → deal_number
    code, deal = req("POST", "/crm/deals", token=sales_tok, body={
        "title": f"编号测试商机-{uuid.uuid4().hex[:6]}",
        "customer_id": cust["id"],
        "amount": 1000,
    })
    results.append(check("VN-7-1 创建商机 201", code == 201, str(code)))
    results.append(check("VN-7-2 商机编号 SJ", (deal.get("deal_number") or "").startswith("SJ"), deal.get("deal_number")))

    # VN-8 创建产品（不传 code）→ 自动生成 CP 编码
    code, prod = req("POST", "/crm/products", token=admin_tok, body={
        "name": f"编号测试产品-{uuid.uuid4().hex[:6]}",
        "unit": "个",
        "list_price": 99,
    })
    results.append(check("VN-8-1 创建产品(无code) 201", code == 201, str(code)))
    results.append(check("VN-8-2 产品编码自动 CP", (prod.get("code") or "").startswith("CP"), prod.get("code")))

    # VN-9 创建报价 → quote_number 用规则
    code, quote = req("POST", "/crm/quotes", token=sales_tok, body={
        "subject": f"编号测试报价-{uuid.uuid4().hex[:6]}",
        "customer_id": cust["id"],
        "deal_id": deal["id"],
        "lines": [],
    })
    results.append(check("VN-9-1 创建报价 201", code == 201, str(code)))
    results.append(check("VN-9-2 报价编号 BJ", (quote.get("quote_number") or "").startswith("BJ"), quote.get("quote_number")))

    # VN-10 修改 lead 规则前缀为 XSHD，再建线索 → 新前缀生效
    code, _ = req("PUT", "/crm/number-rules/lead", token=admin_tok, body={
        "prefix": "XSHD", "seq_width": 4, "reset_period": "once", "enabled": True, "date_format": "%Y%m%d",
    })
    results.append(check("VN-10-1 PUT number-rules/lead 200", code == 200, str(code)))
    code, lead3 = req("POST", "/crm/leads", token=sales_tok, body=lead_body(f"改前缀线索-{uuid.uuid4().hex[:6]}"))
    results.append(check("VN-10-2 新线索用新前缀 XSHD", (lead3.get("lead_number") or "").startswith("XSHD"), lead3.get("lead_number")))
    results.append(check("VN-10-3 新线索序列宽度4", len((lead3.get("lead_number") or "")[-4:]) == 4 and (lead3.get("lead_number") or "")[-4:].isdigit(), lead3.get("lead_number")))

    # VN-11 非法重置周期被拒
    code, _ = req("PUT", "/crm/number-rules/lead", token=admin_tok, body={"reset_period": "hourly"})
    results.append(check("VN-11-1 非法重置周期 422", code == 422, str(code)))

    # VN-12 sales 无权 PUT（403）
    code, _ = req("PUT", "/crm/number-rules/lead", token=sales_tok, body={"prefix": "XS"})
    results.append(check("VN-12-1 sales PUT 规则 403", code == 403, str(code)))

    # 复位 lead 规则为默认，保持开发库整洁
    req("PUT", "/crm/number-rules/lead", token=admin_tok, body={
        "prefix": "XS", "seq_width": 3, "reset_period": "once",
        "date_format": "%Y%m%d", "enabled": True,
    })

    return finish_phase("v0.8编号", results)


if __name__ == "__main__":
    raise SystemExit(main())
