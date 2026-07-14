#!/usr/bin/env python3
"""v0.9 P1 延后项验收：分配 / 地址 / 标签 / 团队 / BANT（054–058）。"""
from __future__ import annotations

import subprocess
import sys
import uuid
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
    results.append(check(f"VP1b-0 alembic={EXPECTED_HEAD}", is_at_expected_head(out), out.strip()))
    results.append(check("VP1b-pre sales owner", bool(sales_owner), str(sales_owner)))

    uniq = uuid.uuid4().hex[:8]
    marker = f"ASSIGN-{uniq}"
    code, rule2 = req(
        "POST",
        "/crm/assignment-rules",
        token=admin_tok,
        body={
            "name": f"精确分配-{uniq}",
            "condition_json": {"field": "company_name", "operator": "contains", "value": marker},
            "assign_type": "fixed_user",
            "target_id": sales_owner,
            "priority": 0,
            "is_active": True,
        },
    )
    results.append(check("VP1-8-1 建分配规则 201", code == 201, f"{code} {rule2}"))
    code, lead_a = req(
        "POST",
        "/crm/leads",
        token=admin_tok,
        body=lead_body(
            f"公司{marker}",
            mobile=f"139{int(uuid.uuid4().hex[:8], 16) % 100000000:08d}",
            source="线下",
        ),
    )
    results.append(check("VP1-8-2 建线索 201", code == 201, f"{code} {lead_a}"))
    results.append(
        check(
            "VP1-8-3 owner=target",
            (lead_a or {}).get("owner_user_id") == sales_owner,
            str(lead_a),
        )
    )

    # VP1-9 地址
    code, cust = req(
        "POST",
        "/crm/customers",
        token=admin_tok,
        body={"company_name": f"地址客户-{uniq}", "mobile": f"138{int(uuid.uuid4().hex[:8], 16) % 100000000:08d}"},
    )
    cust_id = (cust or {}).get("id")
    code, addr = req(
        "POST",
        "/crm/addresses",
        token=admin_tok,
        body={
            "entity_type": "customer",
            "entity_id": cust_id,
            "address_type": "office",
            "address": "上海市浦东新区测试路 1 号",
            "province": "上海",
            "city": "上海",
            "is_default": True,
        },
    )
    results.append(check("VP1-9-1 建地址 201", code == 201, f"{code} {addr}"))
    code, addrs = req("GET", f"/crm/addresses?entity_type=customer&entity_id={cust_id}", token=admin_tok)
    results.append(check("VP1-9-2 列表含地址", code == 200 and isinstance(addrs, list) and len(addrs) >= 1, str(addrs)))

    # VP1-10 标签
    code, tag = req("POST", "/crm/tags", token=admin_tok, body={"name": f"高价值-{uniq}", "color": "#ef4444"})
    results.append(check("VP1-10-1 建标签 201", code == 201, f"{code} {tag}"))
    tag_id = (tag or {}).get("id")
    code, et = req(
        "POST",
        "/crm/entity-tags",
        token=admin_tok,
        body={"entity_type": "customer", "entity_id": cust_id, "tag_id": tag_id},
    )
    results.append(check("VP1-10-2 绑定 201", code == 201, f"{code} {et}"))
    code, cust_get = req("GET", f"/crm/customers/{cust_id}", token=admin_tok)
    tags = (cust_get or {}).get("tags") or []
    results.append(check("VP1-10-3 GET tags 含新标签", any(f"高价值-{uniq}" in str(t) for t in tags), str(tags)))

    # VP1-11 通用团队
    # 先建商机
    code, pipes = req("GET", "/crm/pipelines", token=admin_tok)
    items = (pipes or {}).get("items") if isinstance(pipes, dict) else pipes
    pipe = (items or [None])[0] if items else None
    pid = (pipe or {}).get("id")
    sid = ((pipe or {}).get("stages") or [{}])[0].get("id")
    code, deal = req(
        "POST",
        "/crm/deals",
        token=sales_tok,
        body={"title": f"团队商机-{uniq}", "customer_id": cust_id, "amount": 1000, "pipeline_id": pid, "stage_id": sid, "source": "官网"},
    )
    deal_id = (deal or {}).get("id")
    results.append(check("VP1-11-1 建商机 201", code == 201, f"{code} {deal}"))
    code, members = req("GET", f"/crm/team-members?entity_type=deal&entity_id={deal_id}", token=sales_tok)
    results.append(
        check(
            "VP1-11-2 通用团队含 owner",
            code == 200 and isinstance(members, list) and any(m.get("role") == "owner" for m in members),
            str(members),
        )
    )

    # VP1-12 BANT + 转化建议
    code, lead_b = req(
        "POST",
        "/crm/leads",
        token=sales_tok,
        body=lead_body(f"BANT公司-{uniq}", mobile=f"137{int(uuid.uuid4().hex[:8], 16) % 100000000:08d}", source="电话"),
    )
    lead_b_id = (lead_b or {}).get("id")
    code, bant = req(
        "POST",
        f"/crm/leads/{lead_b_id}/bant",
        token=sales_tok,
        body={"budget_score": 4, "authority_score": 5, "need_score": 3, "time_score": 4, "note": "Q3采购"},
    )
    results.append(check("VP1-12-1 BANT 201", code == 201, f"{code} {bant}"))
    results.append(check("VP1-12-2 total_score", float((bant or {}).get("total_score") or 0) == 4.0, str(bant)))
    code, conv = req(
        "POST",
        f"/crm/leads/{lead_b_id}/convert",
        token=sales_tok,
        body={"force_create": True, "create_deal": True},
    )
    results.append(check("VP1-12-3 转化建商机 201", code == 201 and bool((conv or {}).get("deal_id")), f"{code} {conv}"))
    deal2_id = (conv or {}).get("deal_id")
    code, deal2 = req("GET", f"/crm/deals/{deal2_id}", token=sales_tok)
    results.append(
        check(
            "VP1-12-4 BANT 建议金额",
            code == 200 and float((deal2 or {}).get("amount") or 0) == 80000.0,
            str(deal2),
        )
    )
    results.append(
        check(
            "VP1-12-5 contact_role 决策者",
            (deal2 or {}).get("contact_role") == "决策者",
            str((deal2 or {}).get("contact_role")),
        )
    )

    return finish_phase("v0.9 lead/customer P1b", results)


if __name__ == "__main__":
    raise SystemExit(main())
