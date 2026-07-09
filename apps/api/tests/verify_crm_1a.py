#!/usr/bin/env python3
"""CRM-1a 验收：线索/客户/联系人/跟进（docs/v0.5-crm执行计划.md §3）。"""
from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
WEB_SRC = API_ROOT.parent / "web" / "src"
MP_SRC = API_ROOT.parent / "mp" / "src"
sys.path.insert(0, str(API_ROOT))

from sqlalchemy import inspect

from app.config import settings
from app.database import SessionLocal, engine
from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from tests.verify_crm_helpers import (
    SALES_A_PHONE,
    SALES_B_PHONE,
    admin_token,
    check,
    check_files,
    editor_token,
    ensure_crm_test_users,
    finish_phase,
    lead_body,
    run_pytest,
    run_step_parser,
    sales_token,
)
from tests.http_client import req


def step_1a_1(results: list[bool]) -> None:
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    results.append(check("V1a-1-0 alembic", is_at_expected_head(out), out.strip()[:80]))

    insp = inspect(engine)
    for table in ("leads", "customers", "contacts", "crm_activities"):
        results.append(check(f"V1a-1-1 表 {table}", insp.has_table(table)))

    cols = {c["name"]: c for c in insp.get_columns("leads")}
    results.append(check("V1a-1-1 company_name非空", cols["company_name"]["nullable"] is False))
    results.append(check("V1a-1-2 leads.tenant_id索引", any("tenant_id" in str(i) for i in insp.get_indexes("leads"))))
    results.append(check("V1a-1-3 extra_data列", "extra_data" in cols))
    fks = insp.get_foreign_keys("contacts")
    results.append(
        check(
            "V1a-1-4 contacts.customer_id FK",
            any(fk.get("referred_table") == "customers" for fk in fks),
        )
    )


def step_1a_2(results: list[bool]) -> None:
    results.append(check("V1a-2-4 unit test_crm_scope", run_pytest("tests/unit/test_crm_scope.py")))


def step_1a_3(results: list[bool]) -> None:
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()

    sales_a = sales_token(SALES_A_PHONE, tenant_id)
    sales_b = sales_token(SALES_B_PHONE, tenant_id)
    admin = admin_token()
    editor = editor_token()

    code, lead = req(
        "POST",
        "/crm/leads",
        token=sales_a,
        body={"company_name": "CRM测试公司A", "contact_name": "张三", "mobile": "13800001111"},
    )
    results.append(check("V1a-3-1 sales创建线索", code == 201 and lead.get("company_name"), str(code)))
    lead_id = lead.get("id") if code == 201 else None

    code, _ = req(
        "POST",
        "/crm/leads",
        token=editor,
        body={"company_name": "editor不可建"},
    )
    results.append(check("V1a-3-2 editor无create", code == 403, str(code)))

    if lead_id:
        code, list_b = req("GET", "/crm/leads", token=sales_b)
        ids_b = [x["id"] for x in list_b.get("items", [])] if code == 200 else []
        results.append(check("V1a-3-3 salesB不见A线索", lead_id not in ids_b, str(ids_b[:3])))

        code, list_admin = req("GET", "/crm/leads", token=admin)
        ids_admin = [x["id"] for x in list_admin.get("items", [])] if code == 200 else []
        results.append(check("V1a-3-4 admin见全量", lead_id in ids_admin, str(len(ids_admin))))

        code, _ = req(
            "PATCH",
            f"/crm/leads/{lead_id}",
            token=sales_a,
            body={"owner_user_id": "00000000-0000-0000-0000-000000000001"},
        )
        results.append(check("V1a-3-5 无assign改owner", code == 403, str(code)))

        code, _ = req("DELETE", f"/crm/leads/{lead_id}", token=admin)
        results.append(check("V1a-3-6 admin软删", code == 204, str(code)))
        code, list_after = req("GET", "/crm/leads", token=admin)
        ids_after = [x["id"] for x in list_after.get("items", [])] if code == 200 else []
        results.append(check("V1a-3-6 删后不可见", lead_id not in ids_after))


def step_1a_4(results: list[bool]) -> None:
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()

    sales_a = sales_token(SALES_A_PHONE, tenant_id)
    sales_b = sales_token(SALES_B_PHONE, tenant_id)

    code, cust = req(
        "POST",
        "/crm/customers",
        token=sales_a,
        body={"company_name": "客户A公司", "mobile": "13800002222"},
    )
    results.append(check("V1a-4-1 客户CRUD创建", code == 201, str(code)))
    cust_id = cust.get("id") if code == 201 else None

    if cust_id:
        code, contact = req(
            "POST",
            f"/crm/customers/{cust_id}/contacts",
            token=sales_a,
            body={"name": "李四", "mobile": "13800003333", "is_primary": True},
        )
        results.append(check("V1a-4-2 新建联系人", code == 201, str(code)))

        code, c2 = req(
            "POST",
            f"/crm/customers/{cust_id}/contacts",
            token=sales_a,
            body={"name": "王五", "is_primary": True},
        )
        results.append(check("V1a-4-4 新首要取消旧首要", code == 201, str(code)))
        if code == 201:
            code, contacts = req("GET", f"/crm/customers/{cust_id}/contacts", token=sales_a)
            primaries = [c for c in contacts if c.get("is_primary")] if code == 200 else []
            results.append(check("V1a-4-4 仅一个首要", len(primaries) == 1, str(len(primaries))))

        code, _ = req("GET", f"/crm/customers/{cust_id}/contacts", token=sales_b)
        results.append(check("V1a-4-3 不可见客户403", code in (403, 404), str(code)))


def step_1a_5(results: list[bool]) -> None:
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()

    sales_a = sales_token(SALES_A_PHONE, tenant_id)
    sales_b = sales_token(SALES_B_PHONE, tenant_id)

    code, lead = req(
        "POST",
        "/crm/leads",
        token=sales_a,
        body=lead_body("跟进测试公司", contact_name="测试"),
    )
    lead_id = lead.get("id") if code == 201 else None

    if lead_id:
        code, act = req(
            "POST",
            "/crm/activities",
            token=sales_a,
            body={"lead_id": lead_id, "activity_type": "call", "content": "首次电话"},
        )
        results.append(check("V1a-5-1 写跟进", code == 201, str(code)))

        code, timeline = req("GET", f"/crm/activities?lead_id={lead_id}", token=sales_a)
        results.append(
            check(
                "V1a-5-2 时间线DESC",
                code == 200 and len(timeline) >= 1 and timeline[0].get("content") == "首次电话",
                str(timeline[:1]),
            )
        )

        code, _ = req("GET", f"/crm/activities?lead_id={lead_id}", token=sales_b)
        results.append(check("V1a-5-3 不可见线索403", code == 403, str(code)))

    code, _ = req(
        "POST",
        "/crm/activities",
        token=sales_a,
        body={"lead_id": lead_id, "activity_type": "invalid_type", "content": "x"},
    )
    results.append(check("V1a-5-4 非法activity_type", code == 422, str(code)))


def step_1a_6(results: list[bool]) -> None:
    check_files(
        results,
        "V1a-6-1 Web 页面",
        [
            WEB_SRC / "views" / "crm" / "Leads.vue",
            WEB_SRC / "views" / "crm" / "Customers.vue",
        ],
    )
    router_text = (WEB_SRC / "router.js").read_text(encoding="utf-8")
    results.append(
        check(
            "V1a-6-2 路由",
            "crm/leads" in router_text and "crm/customers" in router_text,
            "router.js",
        )
    )
    perm_text = (WEB_SRC / "config" / "permissions.js").read_text(encoding="utf-8")
    results.append(
        check(
            "V1a-6-3 菜单权限",
            "crm.lead.list_own" in perm_text
            and "crm.customer.list_own" in perm_text
            and "线索" in perm_text
            and "客户" in perm_text,
            "permissions.js NAV",
        )
    )
    client_text = (WEB_SRC / "api" / "client.js").read_text(encoding="utf-8")
    results.append(check("V1a-6-4 crmApi", "export const crmApi" in client_text, "client.js"))


def step_1a_7(results: list[bool]) -> None:
    check_files(
        results,
        "V1a-7-1 H5 页面",
        [
            MP_SRC / "pages" / "crm" / "leads.vue",
            MP_SRC / "pages" / "crm" / "customers.vue",
        ],
    )
    pages_json = (MP_SRC / "pages.json").read_text(encoding="utf-8")
    results.append(
        check(
            "V1a-7-2 pages.json",
            "pages/crm/leads" in pages_json and "pages/crm/customers" in pages_json,
            "pages.json",
        )
    )
    mp_perm = (MP_SRC / "utils" / "permissions.js").read_text(encoding="utf-8")
    results.append(
        check(
            "V1a-7-3 MINE_MENU",
            "crm.lead.list_own" in mp_perm
            and "/pages/crm/leads" in mp_perm
            and "/pages/crm/customers" in mp_perm,
            "permissions.js",
        )
    )


STEPS = {
    "1a-1": step_1a_1,
    "1a-2": step_1a_2,
    "1a-3": step_1a_3,
    "1a-4": step_1a_4,
    "1a-5": step_1a_5,
    "1a-6": step_1a_6,
    "1a-7": step_1a_7,
}


def main() -> int:
    args = run_step_parser(list(STEPS.keys()))
    results: list[bool] = []
    try:
        if args.step:
            STEPS[args.step](results)
        else:
            for fn in STEPS.values():
                fn(results)
    except Exception as e:
        print(f"ERROR: {e}")
        raise
    return finish_phase("1a", results)


if __name__ == "__main__":
    raise SystemExit(main())
