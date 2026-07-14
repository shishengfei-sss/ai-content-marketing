#!/usr/bin/env python3
"""v0.9 线索/客户增强 P0 验收：字段 + source 统一 + 转化拷贝 + contact_role + 附件权限。"""
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
    from app.services.crm.schema_service import ensure_entity_schema

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
        from app.models import User

        admin = db.query(User).filter(User.phone == "13900000099").first()
        if admin and admin.tenant_id:
            for et in ("lead", "customer", "contact"):
                ensure_entity_schema(db, admin.tenant_id, et)
    finally:
        db.close()

    admin_tok = admin_token()
    sales_tok = sales_token()
    results: list[bool] = []

    out = alembic_head()
    results.append(check("VP0-0 alembic=050", is_at_expected_head(out), out.strip()))

    # VP0-1 Lead 4 字段 CRUD
    code, lead = req(
        "POST",
        "/crm/leads",
        token=sales_tok,
        body=lead_body(
            f"P0线索公司-{uuid.uuid4().hex[:6]}",
            contact_name="张三",
            source="官网",
            title="采购经理",
            lead_score=85,
            department="采购部",
            country="中国",
        ),
    )
    results.append(check("VP0-1-1 创建线索(4字段) 201", code == 201, f"{code} {lead}"))
    lead_id = (lead or {}).get("id")
    results.append(check("VP0-1-2 title", (lead or {}).get("title") == "采购经理", str((lead or {}).get("title"))))
    results.append(check("VP0-1-3 lead_score", (lead or {}).get("lead_score") == 85, str((lead or {}).get("lead_score"))))
    results.append(check("VP0-1-4 department", (lead or {}).get("department") == "采购部", str((lead or {}).get("department"))))
    results.append(check("VP0-1-5 country", (lead or {}).get("country") == "中国", str((lead or {}).get("country"))))

    code, lead2 = req("PATCH", f"/crm/leads/{lead_id}", token=sales_tok, body={"lead_score": 72, "title": "总监"})
    results.append(check("VP0-1-6 PATCH lead 200", code == 200, f"{code} {lead2}"))
    results.append(check("VP0-1-7 PATCH score", (lead2 or {}).get("lead_score") == 72, str((lead2 or {}).get("lead_score"))))

    # VP0-2 Customer source / converted_lead_score 可空写入
    code, cust = req(
        "POST",
        "/crm/customers",
        token=admin_tok,
        body={
            "company_name": f"P0客户-{uuid.uuid4().hex[:6]}",
            "mobile": f"139{uuid.uuid4().hex[:8]}"[:11],
            "source": "转介绍",
            "description": "测试客户描述",
            "type": "客户",
            "tags": "高价值,续约",
        },
    )
    results.append(check("VP0-2-1 创建客户 201", code == 201, str(code)))
    cust_id = (cust or {}).get("id")
    results.append(check("VP0-2-2 source", (cust or {}).get("source") == "转介绍", str((cust or {}).get("source"))))
    results.append(check("VP0-2-3 tags list", (cust or {}).get("tags") == ["高价值", "续约"], str((cust or {}).get("tags"))))
    results.append(
        check(
            "VP0-2-4 converted_lead_score 默认可空",
            (cust or {}).get("converted_lead_score") is None,
            str((cust or {}).get("converted_lead_score")),
        )
    )

    # VP0-3 转化拷贝 source + converted_lead_score + 级别
    code, lead_c = req(
        "POST",
        "/crm/leads",
        token=sales_tok,
        body=lead_body(
            f"转化公司-{uuid.uuid4().hex[:6]}",
            contact_name="李四",
            source="Webhook",
            lead_score=90,
            title="CTO",
            department="技术部",
        ),
    )
    results.append(check("VP0-3-1 待转化线索 201", code == 201, f"{code} {lead_c}"))
    lead_c_id = (lead_c or {}).get("id")
    code, conv = req("POST", f"/crm/leads/{lead_c_id}/convert", token=sales_tok)
    results.append(check("VP0-3-2 转化 201", code == 201, f"{code} {conv}"))
    conv_cust_id = (conv or {}).get("customer_id")
    code, conv_cust = req("GET", f"/crm/customers/{conv_cust_id}", token=sales_tok)
    results.append(check("VP0-3-3 GET 转化客户 200", code == 200, str(code)))
    results.append(
        check(
            "VP0-3-4 source 拷贝",
            (conv_cust or {}).get("source") == "Webhook",
            str((conv_cust or {}).get("source")),
        )
    )
    results.append(
        check(
            "VP0-3-5 converted_lead_score",
            (conv_cust or {}).get("converted_lead_score") == 90,
            str((conv_cust or {}).get("converted_lead_score")),
        )
    )
    level = ((conv_cust or {}).get("extra_data") or {}).get("customer_level")
    results.append(check("VP0-3-6 级别映射 A重点", level == "A重点", str(level)))

    # VP0-4 Contact contact_role；is_decision_maker 列不存在
    code, contact = req(
        "POST",
        f"/crm/customers/{cust_id}/contacts",
        token=admin_tok,
        body={"name": f"联系人-{uuid.uuid4().hex[:4]}", "contact_role": "决策者", "is_primary": True},
    )
    results.append(check("VP0-4-1 创建联系人 contact_role 201", code == 201, str(code)))
    results.append(
        check("VP0-4-2 contact_role 回写", (contact or {}).get("contact_role") == "决策者", str((contact or {}).get("contact_role")))
    )
    results.append(
        check(
            "VP0-4-3 无 is_decision_maker 字段",
            "is_decision_maker" not in (contact or {}),
            str(contact),
        )
    )

    from app.database import engine
    from sqlalchemy import inspect

    insp = inspect(engine)
    contact_cols = {c["name"] for c in insp.get_columns("contacts")}
    results.append(check("VP0-4-4 DB 无 is_decision_maker 列", "is_decision_maker" not in contact_cols, str(contact_cols)))
    results.append(check("VP0-4-5 DB 有 contact_role 列", "contact_role" in contact_cols, str(contact_cols)))

    # VP0-5 DEAL/LEAD 来源均可接受 Webhook
    code, pipes = req("GET", "/crm/pipelines", token=sales_tok)
    pipe = (pipes or [{}])[0]
    pipe_id = pipe.get("id")
    stage_id = (pipe.get("stages") or [{}])[0].get("id")
    code, deal = req(
        "POST",
        "/crm/deals",
        token=sales_tok,
        body={
            "title": f"P0商机-{uuid.uuid4().hex[:6]}",
            "customer_id": cust_id,
            "pipeline_id": pipe_id,
            "stage_id": stage_id,
            "amount": 1000,
            "source": "Webhook",
        },
    )
    results.append(check("VP0-5-1 Deal source=Webhook 201", code == 201, str(code)))
    results.append(check("VP0-5-2 Lead source=Webhook 已创建", bool(lead_c_id), str(lead_c_id)))

    # VP0-6 Lead/Customer 附件列表（复用 042）
    code, att_list = req(
        "GET",
        f"/crm/attachments?entity_type=lead&entity_id={lead_id}",
        token=sales_tok,
    )
    results.append(check("VP0-6-1 Lead 附件列表 200", code == 200, str(code)))
    results.append(check("VP0-6-2 Lead 附件列表为数组", isinstance(att_list, list), str(type(att_list))))

    from tests.http_client import _get_test_client

    client = _get_test_client()
    up = client.post(
        f"/api/v1/crm/attachments?entity_type=customer&entity_id={cust_id}",
        headers={"Authorization": f"Bearer {admin_tok}"},
        files={"file": ("p0-test.txt", b"hello p0", "text/plain")},
    )
    results.append(check("VP0-6-3 Customer 上传附件 201", up.status_code == 201, f"{up.status_code} {up.text[:200]}"))
    code, att_list2 = req(
        "GET",
        f"/crm/attachments?entity_type=customer&entity_id={cust_id}",
        token=admin_tok,
    )
    results.append(check("VP0-6-4 Customer 附件列表含文件", code == 200 and len(att_list2 or []) >= 1, str(att_list2)))

    return finish_phase("v0.9 lead/customer P0", results)


if __name__ == "__main__":
    raise SystemExit(main())
