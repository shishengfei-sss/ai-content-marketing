#!/usr/bin/env python3
"""CRM-1c 验收：任务 + 转化 + 工作台（docs/v0.5-crm执行计划.md §5）。"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = API_ROOT.parent / "web" / "src"
MP_SRC = API_ROOT.parent / "mp" / "src"
sys.path.insert(0, str(API_ROOT))

from sqlalchemy import inspect

from app.database import SessionLocal, engine
from app.models import TenantMembership, User
from app.permissions import SYSTEM_ROLE_SALES_MANAGER
from tests.alembic_head import is_at_expected_head
from tests.verify_crm_helpers import (
    SALES_A_PHONE,
    SALES_B_PHONE,
    admin_token,
    check,
    check_files,
    editor_token,
    ensure_crm_test_users,
    finish_phase,
    req,
    run_step_parser,
    sales_token,
)

SALES_MGR_PHONE = "13900001003"


def _ensure_sales_manager(db) -> None:
    from app.models import TenantRole
    from app.services.auth_service import hash_password
    from app.services.membership_service import get_membership

    base = ensure_crm_test_users(db)
    tenant_id = uuid.UUID(base["tenant_id"])
    mgr_role = (
        db.query(TenantRole)
        .filter(TenantRole.tenant_id == tenant_id, TenantRole.code == SYSTEM_ROLE_SALES_MANAGER)
        .first()
    )
    user = db.query(User).filter(User.phone == SALES_MGR_PHONE).first()
    if not user:
        user = User(
            phone=SALES_MGR_PHONE,
            hashed_password=hash_password("Test123456"),
            display_name="销售经理",
            role="user",
            is_active=True,
        )
        db.add(user)
        db.flush()
    user.tenant_id = tenant_id
    membership = get_membership(db, user.id, tenant_id)
    if not membership:
        db.add(
            TenantMembership(user_id=user.id, tenant_id=tenant_id, role_id=mgr_role.id, is_active=True)
        )
    else:
        membership.role_id = mgr_role.id
    db.commit()


def step_1c_1(results: list[bool]) -> None:
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    results.append(check("V1c-1-0 alembic", is_at_expected_head(out), out.strip()[:60]))
    results.append(check("V1c-1-1 表 crm_tasks", inspect(engine).has_table("crm_tasks")))

    db = SessionLocal()
    try:
        ensure_crm_test_users(db)
        _ensure_sales_manager(db)
    finally:
        db.close()

    sales_a = sales_token(SALES_A_PHONE)
    sales_b = sales_token(SALES_B_PHONE)
    mgr = sales_token(SALES_MGR_PHONE)

    code, me = req("GET", "/auth/me", token=sales_a)
    my_id = me["id"]

    code, task = req(
        "POST",
        "/crm/tasks",
        token=sales_a,
        body={"title": f"跟进-{uuid.uuid4().hex[:6]}"},
    )
    results.append(check("V1c-1-1 创建任务", code == 201, str(code)))
    results.append(check("V1c-1-1 assignee默认本人", task.get("assignee_user_id") == my_id, str(task.get("assignee_user_id"))))

    code, _ = req(
        "PATCH",
        f"/crm/tasks/{task['id']}",
        token=sales_a,
        body={"assignee_user_id": str(uuid.uuid4())},
    )
    results.append(check("V1c-1-2 sales不能assign", code == 403, str(code)))

    code, me_b = req("GET", "/auth/me", token=sales_b)
    code, assigned = req(
        "PATCH",
        f"/crm/tasks/{task['id']}",
        token=mgr,
        body={"assignee_user_id": me_b["id"]},
    )
    results.append(check("V1c-1-3 manager可assign", code == 200, str(code)))
    results.append(check("V1c-1-3 assignee已改", assigned.get("assignee_user_id") == me_b["id"], str(assigned)))


def step_1c_2(results: list[bool]) -> None:
    sales_a = sales_token(SALES_A_PHONE)
    editor = editor_token()

    code, lead = req(
        "POST",
        "/crm/leads",
        token=sales_a,
        body={
            "company_name": f"转化测试-{uuid.uuid4().hex[:6]}",
            "contact_name": "张经理",
            "mobile": "13800138000",
        },
    )
    results.append(check("V1c-2-0 建线索", code == 201, str(code)))

    code, conv = req("POST", f"/crm/leads/{lead['id']}/convert", token=editor)
    results.append(check("V1c-2-4 editor无convert403", code == 403, str(code)))

    code, conv = req("POST", f"/crm/leads/{lead['id']}/convert", token=sales_a)
    results.append(check("V1c-2-1 转化201", code == 201, str(code)))

    code, lead_after = req("GET", f"/crm/leads/{lead['id']}", token=sales_a)
    results.append(check("V1c-2-1 线索已转化", lead_after.get("status") == "已转化", lead_after.get("status")))

    code, customer = req("GET", f"/crm/customers/{conv['customer_id']}", token=sales_a)
    results.append(
        check(
            "V1c-2-1 converted_from",
            str(customer.get("converted_from_lead_id")) == lead["id"],
            str(customer.get("converted_from_lead_id")),
        )
    )

    code, contacts = req("GET", f"/crm/customers/{conv['customer_id']}/contacts", token=sales_a)
    results.append(check("V1c-2-2 有联系人", len(contacts) >= 1, str(len(contacts))))
    if contacts:
        results.append(check("V1c-2-2 联系人姓名", contacts[0].get("name") == "张经理", contacts[0].get("name")))

    code, _ = req("POST", f"/crm/leads/{lead['id']}/convert", token=sales_a)
    results.append(check("V1c-2-3 重复转化409", code == 409, str(code)))


def step_1c_3(results: list[bool]) -> None:
    admin = admin_token()
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        _ensure_sales_manager(db)
        sales_a_mid = (
            db.query(TenantMembership)
            .join(User, User.id == TenantMembership.user_id)
            .filter(User.phone == SALES_A_PHONE, TenantMembership.tenant_id == uuid.UUID(ctx["tenant_id"]))
            .first()
        )
        mgr_mid = (
            db.query(TenantMembership)
            .join(User, User.id == TenantMembership.user_id)
            .filter(User.phone == SALES_MGR_PHONE, TenantMembership.tenant_id == uuid.UUID(ctx["tenant_id"]))
            .first()
        )
        if sales_a_mid and mgr_mid:
            req(
                "PATCH",
                f"/crm/sales-profiles/{sales_a_mid.id}",
                token=admin,
                body={"reports_to_membership_id": str(mgr_mid.id)},
            )
    finally:
        db.close()

    sales_a = sales_token(SALES_A_PHONE)
    sales_b = sales_token(SALES_B_PHONE)
    mgr = sales_token(SALES_MGR_PHONE)

    due = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    req("POST", "/crm/tasks", token=sales_a, body={"title": "A今日任务", "due_at": due})
    req("POST", "/crm/tasks", token=sales_b, body={"title": "B今日任务", "due_at": due})

    code, stats_a = req("GET", "/dashboard/stats", token=sales_a)
    results.append(check("V1c-3-1 sales stats", code == 200, str(code)))
    a_due = stats_a.get("crm_tasks_due_today", 0)

    code, stats_b = req("GET", "/dashboard/stats", token=sales_b)
    b_due = stats_b.get("crm_tasks_due_today", 0)

    code, stats_mgr = req("GET", "/dashboard/stats", token=mgr)
    mgr_due = stats_mgr.get("crm_tasks_due_today", 0)

    results.append(check("V1c-3-1 A仅见本人", a_due >= 1, str(a_due)))
    results.append(check("V1c-3-1 B仅见本人", b_due >= 1, str(b_due)))
    results.append(check("V1c-3-2 manager>=A", mgr_due >= a_due, f"mgr={mgr_due} a={a_due}"))


def step_1c_4(results: list[bool]) -> None:
    check_files(results, "V1c-4-1 Tasks", [WEB_SRC / "views" / "crm" / "Tasks.vue"])
    lead_detail = (WEB_SRC / "views" / "crm" / "LeadDetail.vue").read_text(encoding="utf-8")
    results.append(check("V1c-4-1 详情Tab任务", "任务" in lead_detail, "LeadDetail.vue"))
    router_text = (WEB_SRC / "router.js").read_text(encoding="utf-8")
    results.append(check("V1c-4-2 任务路由", "crm/tasks" in router_text, "router.js"))


def step_1c_5(results: list[bool]) -> None:
    check_files(results, "V1c-5-1 H5任务", [MP_SRC / "pages" / "crm" / "tasks.vue"])
    pages = (MP_SRC / "pages.json").read_text(encoding="utf-8")
    results.append(check("V1c-5-1 pages.json", "pages/crm/tasks" in pages, "pages.json"))


def step_1c_6(results: list[bool]) -> None:
    step_1c_1(results)
    step_1c_2(results)
    step_1c_3(results)
    step_1c_4(results)
    step_1c_5(results)


STEPS = {
    "1c-1": step_1c_1,
    "1c-2": step_1c_2,
    "1c-3": step_1c_3,
    "1c-4": step_1c_4,
    "1c-5": step_1c_5,
    "1c-6": step_1c_6,
}


def main() -> int:
    args = run_step_parser(list(STEPS.keys()))
    results: list[bool] = []
    try:
        if args.step:
            STEPS[args.step](results)
        else:
            for key in ("1c-1", "1c-2", "1c-3", "1c-4", "1c-5"):
                STEPS[key](results)
    except Exception as e:
        print(f"ERROR: {e}")
        raise
    return finish_phase("1c", results)


if __name__ == "__main__":
    raise SystemExit(main())
