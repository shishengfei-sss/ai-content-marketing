#!/usr/bin/env python3
"""v0.9 P2 验收：通知/漏斗/导出（059）+ UTM/ROI/培育（060–061）+ 生命周期/决策链/工商（062）。"""
from __future__ import annotations

import subprocess
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
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
    from app.models.crm import Customer

    db = SessionLocal()
    try:
        phones = ensure_crm_test_users(db)
        sales_owner = phones.get("13900001001")
    finally:
        db.close()

    admin_tok = admin_token()
    sales_tok = sales_token()
    results: list[bool] = []

    out = alembic_head()
    results.append(check(f"VP2-0 alembic={EXPECTED_HEAD}", is_at_expected_head(out), out.strip()))

    # VP2-1 分配触发通知
    marker = f"P2N-{uuid.uuid4().hex[:6]}"
    code, _ = req(
        "POST",
        "/crm/assignment-rules",
        token=admin_tok,
        body={
            "name": f"通知规则-{marker}",
            "condition_json": {"field": "company_name", "operator": "contains", "value": marker},
            "assign_type": "fixed_user",
            "target_id": sales_owner,
            "priority": 0,
            "is_active": True,
        },
    )
    results.append(check("VP2-1-1 建分配规则", code == 201, str(code)))
    code, _ = req(
        "POST",
        "/crm/leads",
        token=admin_tok,
        body=lead_body(
            f"公司{marker}",
            mobile=f"139{int(uuid.uuid4().hex[:8], 16) % 100000000:08d}",
            source="线下",
        ),
    )
    results.append(check("VP2-1-2 建线索触发分配", code == 201, str(code)))
    code, notes = req("GET", "/crm/notifications?unread_only=true", token=sales_tok)
    items = (notes or {}).get("items") if isinstance(notes, dict) else []
    results.append(check("VP2-1-3 销售有未读通知", code == 200 and len(items) >= 1, str(notes)))
    code, unread = req("GET", "/crm/notifications/unread-count", token=sales_tok)
    results.append(check("VP2-1-4 unread-count", code == 200 and (unread or {}).get("count", 0) >= 1, str(unread)))
    if items:
        nid = items[0].get("id")
        code, _ = req("POST", f"/crm/notifications/{nid}/read", token=sales_tok)
        results.append(check("VP2-1-5 标记已读", code == 200, str(code)))

    # VP2-2 漏斗 + 看板
    code, funnel = req("GET", "/analytics/lead-funnel", token=admin_tok)
    results.append(check("VP2-2-1 lead-funnel 200", code == 200, str(code)))
    results.append(
        check(
            "VP2-2-2 stages",
            isinstance(funnel, dict) and isinstance(funnel.get("stages"), list) and len(funnel["stages"]) >= 3,
            str(funnel),
        )
    )
    code, board = req("GET", "/analytics/sales-board", token=sales_tok)
    results.append(check("VP2-2-3 sales-board 200", code == 200, str(code)))
    results.append(
        check(
            "VP2-2-4 board keys",
            isinstance(board, dict) and "open_leads" in (board or {}) and "won_amount" in (board or {}),
            str(board),
        )
    )

    # VP2-3 导出
    code, csv_body = req("GET", "/crm/export/leads?format=csv", token=admin_tok)
    results.append(check("VP2-3-1 export leads csv 200", code == 200, f"{code} type={type(csv_body)}"))
    code, cust_csv = req("GET", "/crm/export/customers?format=csv", token=admin_tok)
    results.append(check("VP2-3-2 export customers csv 200", code == 200, str(code)))
    code, xlsx = req("GET", "/crm/export/leads?format=xlsx", token=admin_tok)
    results.append(check("VP2-3-3 export leads xlsx 200", code == 200, str(code)))

    # VP2-4 UTM 解析 + source-roi
    landing = "https://example.com/lp?utm_source=wechat&utm_medium=cpc&utm_campaign=spring"
    code, lead = req(
        "POST",
        "/crm/leads",
        token=admin_tok,
        body=lead_body(
            f"UTM公司-{uuid.uuid4().hex[:6]}",
            landing_url=landing,
            acquisition_cost=50,
        ),
    )
    results.append(check("VP2-4-1 创建含 landing_url", code == 201, str(code)))
    results.append(
        check(
            "VP2-4-2 UTM 字段解析",
            isinstance(lead, dict)
            and lead.get("utm_source") == "wechat"
            and lead.get("utm_medium") == "cpc"
            and lead.get("source") == "公众号"
            and lead.get("acquisition_cost") is not None,
            str(lead),
        )
    )
    code, roi = req("GET", "/analytics/source-roi", token=admin_tok)
    items_roi = (roi or {}).get("items") if isinstance(roi, dict) else None
    results.append(
        check(
            "VP2-4-3 source-roi",
            code == 200 and isinstance(items_roi, list) and len(items_roi) >= 1,
            str(roi),
        )
    )

    # VP2-5 培育规则 run → create_task
    nurture_marker = f"NUR-{uuid.uuid4().hex[:6]}"
    code, rule = req(
        "POST",
        "/crm/nurture-rules",
        token=admin_tok,
        body={
            "name": f"低分培育-{nurture_marker}",
            "condition_json": {"field": "company_name", "operator": "contains", "value": nurture_marker},
            "action_type": "create_task",
            "action_config": {"title": f"培育任务-{nurture_marker}"},
            "priority": 0,
            "is_active": True,
        },
    )
    results.append(check("VP2-5-1 建培育规则", code == 201, str(code)))
    code, nurture_lead = req(
        "POST",
        "/crm/leads",
        token=admin_tok,
        body=lead_body(f"{nurture_marker}-公司", lead_score=20),
    )
    results.append(check("VP2-5-2 建低分线索", code == 201, str(code)))
    code, run = req("POST", "/crm/nurture-rules/run?limit=100", token=admin_tok)
    results.append(
        check(
            "VP2-5-3 run 触发动作",
            code == 200 and isinstance(run, dict) and (run.get("actions") or 0) >= 1,
            str(run),
        )
    )
    code, tasks = req("GET", f"/crm/tasks?q={nurture_marker}", token=admin_tok)
    task_items = (tasks or {}).get("items") if isinstance(tasks, dict) else tasks
    if not isinstance(task_items, list):
        task_items = []
    hit = any(nurture_marker in str(t.get("title") or "") for t in task_items)
    results.append(check("VP2-5-4 产出培育任务", code == 200 and hit, str(tasks)[:400]))

    # VP2-6 生命周期 / 决策链 / 工商 stub
    code, cust = req(
        "POST",
        "/crm/customers",
        token=admin_tok,
        body={"company_name": f"生命周期客户-{uuid.uuid4().hex[:6]}", "status": "成交"},
    )
    results.append(check("VP2-6-1 建客户", code == 201, str(code)))
    cid = (cust or {}).get("id")
    if cid:
        db = SessionLocal()
        try:
            row = db.query(Customer).filter(Customer.id == uuid.UUID(str(cid))).first()
            if row:
                row.last_deal_date = date.today() - timedelta(days=10)
                db.commit()
        finally:
            db.close()
    code, life = req("GET", "/analytics/lifecycle-report", token=admin_tok)
    buckets = (life or {}).get("buckets") if isinstance(life, dict) else None
    results.append(
        check(
            "VP2-6-2 lifecycle-report",
            code == 200 and isinstance(buckets, dict) and (buckets.get("新客户") or 0) >= 1,
            str(life),
        )
    )

    code, c1 = req(
        "POST",
        f"/crm/customers/{cid}/contacts",
        token=admin_tok,
        body={"name": "决策者甲", "contact_role": "决策者", "is_primary": True},
    )
    results.append(check("VP2-6-3 建决策者联系人", code == 201, str(code)))
    boss_id = (c1 or {}).get("id")
    code, c2 = req(
        "POST",
        f"/crm/customers/{cid}/contacts",
        token=admin_tok,
        body={"name": "使用者乙", "contact_role": "使用者", "reports_to_contact_id": boss_id},
    )
    results.append(check("VP2-6-4 建汇报下属", code == 201 and (c2 or {}).get("reports_to_contact_id") == boss_id, str(c2)))
    code, chain = req("GET", f"/crm/customers/{cid}/decision-chain", token=admin_tok)
    results.append(
        check(
            "VP2-6-5 decision-chain",
            code == 200
            and isinstance(chain, dict)
            and len(chain.get("nodes") or []) >= 2
            and len(chain.get("edges") or []) >= 1,
            str(chain),
        )
    )
    code, biz = req(
        "GET",
        f"/crm/customers/business-lookup?company_name={uuid.uuid4().hex[:8]}科技有限公司",
        token=admin_tok,
    )
    results.append(
        check(
            "VP2-6-6 business-lookup stub",
            code == 200 and isinstance(biz, dict) and biz.get("available") is True and biz.get("credit_code"),
            str(biz),
        )
    )

    return finish_phase("v0.9 lead/customer P2", results)


if __name__ == "__main__":
    raise SystemExit(main())
