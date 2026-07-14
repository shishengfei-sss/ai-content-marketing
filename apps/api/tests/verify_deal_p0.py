#!/usr/bin/env python3
"""v0.8 商机增强 P0 验收：阶段 color/is_closed_stage + Deal 6 字段 + source 中文 + 联系人关联。"""
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

    # VP0-0 迁移 head = 040
    out = alembic_head()
    results.append(check("VP0-0 alembic=040", is_at_expected_head(out), out.strip()))

    # 准备：取默认管道与第一阶段
    code, pipes = req("GET", "/crm/pipelines", token=sales_tok)
    results.append(check("VP0-pre GET pipelines 200", code == 200, str(code)))
    pipe = (pipes or [{}])[0]
    pipe_id = pipe.get("id")
    first_stage = (pipe.get("stages") or [{}])[0]
    stage_id = first_stage.get("id")
    results.append(check("VP0-pre 存在默认管道与阶段", bool(pipe_id and stage_id), f"{pipe_id}/{stage_id}"))

    # 准备客户
    code, cust = req("POST", "/crm/customers", token=admin_tok, body={
        "company_name": f"P0客户-{uuid.uuid4().hex[:6]}",
        "mobile": f"139{uuid.uuid4().hex[:8]}"[:11],
    })
    results.append(check("VP0-pre 创建客户 201", code == 201, str(code)))
    cust_id = cust.get("id")

    # VP0-1 阶段 color 持久化：创建阶段带 color
    code, stage = req("POST", f"/crm/pipelines/{pipe_id}/stages", token=admin_tok, body={
        "name": f"P0阶段-{uuid.uuid4().hex[:4]}",
        "sort_order": 999,
        "probability": 10,
        "color": "#ABCDEF",
        "is_closed_stage": False,
    })
    results.append(check("VP0-1-1 创建阶段带color 201", code == 201, str(code)))
    results.append(check("VP0-1-2 color 持久化", (stage or {}).get("color") == "#ABCDEF", str((stage or {}).get("color"))))
    results.append(check("VP0-2 is_closed_stage 持久化(默认false)", (stage or {}).get("is_closed_stage") is False, str((stage or {}).get("is_closed_stage"))))
    new_stage_id = (stage or {}).get("id")

    # VP0-3 Deal 6 字段写入
    code, deal = req("POST", "/crm/deals", token=sales_tok, body={
        "title": f"P0商机-{uuid.uuid4().hex[:6]}",
        "customer_id": cust_id,
        "pipeline_id": pipe_id,
        "stage_id": stage_id,
        "amount": 5000,
        "description": "客户需要一套内容营销系统",
        "next_step": "下周安排产品演示",
        "deal_type": "新业务",
        "priority": "high",
        "competitor": "友商A",
        "contact_role": "决策者",
        "source": "官网",
    })
    results.append(check("VP0-3-1 创建商机(6字段) 201", code == 201, str(code)))
    deal_id = (deal or {}).get("id")
    results.append(check("VP0-3-2 description 回写", (deal or {}).get("description") == "客户需要一套内容营销系统", str((deal or {}).get("description"))))
    results.append(check("VP0-3-3 next_step 回写", (deal or {}).get("next_step") == "下周安排产品演示", str((deal or {}).get("next_step"))))
    results.append(check("VP0-3-4 deal_type 回写", (deal or {}).get("deal_type") == "新业务", str((deal or {}).get("deal_type"))))
    results.append(check("VP0-3-5 priority 回写", (deal or {}).get("priority") == "high", str((deal or {}).get("priority"))))
    results.append(check("VP0-3-6 competitor 回写", (deal or {}).get("competitor") == "友商A", str((deal or {}).get("competitor"))))
    results.append(check("VP0-3-7 contact_role 回写", (deal or {}).get("contact_role") == "决策者", str((deal or {}).get("contact_role"))))

    # VP0-4 source 中文值创建成功（后端 DEAL_SOURCES 含“官网”）
    results.append(check("VP0-4 source=官网 创建成功", code == 201 and (deal or {}).get("source") == "官网", str((deal or {}).get("source"))))

    # VP0-5 联系人关联：为客户创建联系人，再 PATCH 商机 contact_id
    code, contact = req("POST", f"/crm/customers/{cust_id}/contacts", token=admin_tok, body={
        "name": f"P0联系人-{uuid.uuid4().hex[:4]}",
        "mobile": f"138{uuid.uuid4().hex[:8]}"[:11],
    })
    results.append(check("VP0-5-1 创建联系人 201", code == 201, str(code)))
    contact_id = (contact or {}).get("id")
    code, deal2 = req("PATCH", f"/crm/deals/{deal_id}", token=sales_tok, body={"contact_id": contact_id})
    results.append(check("VP0-5-2 PATCH contact_id 200", code == 200, str(code)))
    results.append(check("VP0-5-3 联系人关联回写", (deal2 or {}).get("contact_id") == contact_id, str((deal2 or {}).get("contact_id"))))

    # VP0-3-8 GET 详情含 6 字段
    code, detail = req("GET", f"/crm/deals/{deal_id}", token=sales_tok)
    results.append(check("VP0-3-9 GET 详情含 description", (detail or {}).get("description") == "客户需要一套内容营销系统", str((detail or {}).get("description"))))

    # VP0-6 PATCH 更新 6 字段
    code, upd = req("PATCH", f"/crm/deals/{deal_id}", token=sales_tok, body={
        "priority": "low", "next_step": "寄送方案", "competitor": "友商B",
    })
    results.append(check("VP0-6-1 PATCH 6字段 200", code == 200, str(code)))
    results.append(check("VP0-6-2 priority 更新", (upd or {}).get("priority") == "low", str((upd or {}).get("priority"))))
    results.append(check("VP0-6-3 competitor 更新", (upd or {}).get("competitor") == "友商B", str((upd or {}).get("competitor"))))

    # VP0-7 schema 种子：ensure_entity_schema 后 deal 字段含新字段
    code, schema = req("GET", "/crm/schema/deal", token=sales_tok)
    field_keys = {f.get("field_key") for f in (schema or {}).get("fields", []) if f.get("field_key")}
    for k in ["description", "next_step", "deal_type", "priority", "competitor", "contact_role"]:
        results.append(check(f"VP0-7 schema 含 {k}", k in field_keys, str(k in field_keys)))

    return finish_phase("v0.8-deal-P0", results)


if __name__ == "__main__":
    raise SystemExit(main())
