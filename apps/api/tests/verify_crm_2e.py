#!/usr/bin/env python3
"""CRM-2e 验收：v0.5 缺口补齐（docs/v0.5-crm-gap执行计划.md）。"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = API_ROOT.parent / "web" / "src"
MP_SRC = API_ROOT.parent / "mp" / "src"
sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal
from tests.verify_crm_helpers import (
    SALES_A_PHONE,
    SALES_B_PHONE,
    admin_token,
    check,
    check_files,
    ensure_crm_test_users,
    finish_phase,
    lead_body,
    req,
    run_step_parser,
    sales_token,
)


def _client_upload(token: str, entity_type: str, csv_text: str, filename: str = "import.csv"):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (filename, csv_text.encode("utf-8-sig"), "text/csv")}
    data = {"entity_type": entity_type}
    r = client.post("/api/v1/crm/import/jobs", headers=headers, files=files, data=data)
    try:
        body = r.json()
    except Exception:
        body = r.text
    return r.status_code, body


def _read(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _file_has(path: Path, *needles: str) -> bool:
    text = _read(path)
    return bool(text) and all(n in text for n in needles)


def step_2e_1(results: list[bool]) -> None:
    """工作台 CRM 指标 + 快捷入口。"""
    token = admin_token()
    code, stats = req("GET", "/dashboard/stats", token=token)
    results.append(check("V2e-1-1 stats API", code == 200, str(code)))
    for key in ("crm_new_leads", "crm_tasks_due_today", "crm_tasks_overdue"):
        results.append(check(f"V2e-1-1 含 {key}", key in stats and isinstance(stats[key], int), str(stats.get(key))))

    dash = WEB_SRC / "views" / "Dashboard.vue"
    text = _read(dash)
    crm_cards = ("crm_new_leads" in text) or ("新线索" in text and "crm_tasks" in text)
    results.append(check("V2e-1-2 Dashboard CRM 卡片", crm_cards, dash.name))
    results.append(
        check(
            "V2e-1-3 快捷入口线索",
            "/crm/leads" in text,
            "need /crm/leads in Dashboard.vue shortcuts",
        )
    )
    results.append(
        check(
            "V2e-1-4 快捷入口任务",
            "/crm/tasks" in text,
            "need /crm/tasks in Dashboard.vue shortcuts",
        )
    )


def step_2e_2(results: list[bool]) -> None:
    """跟进 next_follow_up + 最后跟进回写。"""
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
        sales_user_id = ctx[SALES_A_PHONE]
    finally:
        db.close()

    token = sales_token(SALES_A_PHONE, tenant_id)
    tag = uuid.uuid4().hex[:6]
    code, lead = req(
        "POST",
        "/crm/leads",
        token=token,
        body={"company_name": f"跟进回写-{tag}", "contact_name": "张经理", "mobile": f"139{int(tag, 16) % 100000000:08d}", "status": "待跟进"},
    )
    results.append(check("V2e-2-0 创建线索", code == 201, str(code)))
    lead_id = lead.get("id")
    next_at = "2026-12-01T10:00:00+00:00"
    code, act = req(
        "POST",
        "/crm/activities",
        token=token,
        body={
            "lead_id": lead_id,
            "activity_type": "call",
            "content": f"验收跟进-{tag}",
            "next_follow_up_at": next_at,
        },
    )
    results.append(check("V2e-2-1 POST 含 next_follow_up_at", code == 201, f"{code} {act}"))

    code, lead2 = req("GET", f"/crm/leads/{lead_id}", token=token)
    results.append(check("V2e-2-2 线索 next_follow_up_at", code == 200 and lead2.get("next_follow_up_at"), str(lead2.get("next_follow_up_at"))))
    extra = lead2.get("extra_data") or {}
    results.append(
        check(
            "V2e-2-3 last_follow_up_at",
            bool(extra.get("last_follow_up_at")),
            str(extra.get("last_follow_up_at")),
        )
    )
    results.append(
        check(
            "V2e-2-4 last_follow_up_content",
            tag in str(extra.get("last_follow_up_content", "")),
            str(extra.get("last_follow_up_content")),
        )
    )

    code, act2 = req(
        "POST",
        "/crm/activities",
        token=token,
        body={
            "lead_id": lead_id,
            "activity_type": "visit",
            "content": f"状态变更-{tag}",
            "status": "跟进中",
        },
    )
    results.append(check("V2e-2-5 POST 含 status", code == 201, f"{code} {act2}"))
    code, lead3 = req("GET", f"/crm/leads/{lead_id}", token=token)
    results.append(check("V2e-2-5 线索 status=跟进中", code == 200 and lead3.get("status") == "跟进中", str(lead3.get("status"))))


def step_2e_3(results: list[bool]) -> None:
    """客户列表 view_id + list_fields。"""
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()

    token = sales_token(SALES_A_PHONE, tenant_id)
    tag = uuid.uuid4().hex[:6]
    req(
        "POST",
        "/crm/customers",
        token=token,
        body={"company_name": f"视图客户A-{tag}", "status": "潜在"},
    )
    req(
        "POST",
        "/crm/customers",
        token=token,
        body={"company_name": f"视图客户B-{tag}", "status": "成交"},
    )

    code, all_rows = req("GET", "/crm/customers?page_size=100", token=token)
    total_all = all_rows.get("total", 0)

    code, view = req(
        "POST",
        "/crm/views",
        token=token,
        body={
            "entity_type": "customer",
            "name": f"仅潜在-{tag}",
            "filters": {"logic": "and", "conditions": [{"field_key": "status", "op": "eq", "value": "潜在"}]},
        },
    )
    results.append(check("V2e-3-0 创建客户视图", code == 201, str(code)))
    view_id = view.get("id")

    code, filtered = req("GET", f"/crm/customers?view_id={view_id}&page_size=100", token=token)
    results.append(check("V2e-3-1 view_id 200", code == 200, str(code)))
    results.append(check("V2e-3-1 含 list_fields", isinstance(filtered.get("list_fields"), list), str(filtered.get("list_fields"))[:80]))
    results.append(
        check(
            "V2e-3-2 筛选生效",
            filtered.get("total", total_all) <= total_all and filtered.get("total", 0) >= 1,
            f"filtered={filtered.get('total')} all={total_all}",
        )
    )
    results.append(check("V2e-3-3 响应含 view_id", filtered.get("view_id") == view_id, str(filtered.get("view_id"))))


def step_2e_4(results: list[bool]) -> None:
    """客户详情 Web + API 串联。"""
    check_files(results, "V2e-4-1", [WEB_SRC / "views" / "crm" / "CustomerDetail.vue"])
    router = _read(WEB_SRC / "router.js")
    results.append(check("V2e-4-1 路由 customers/:id", "crm/customers/:id" in router or "customers/:id" in router, "router"))
    customers_vue = _read(WEB_SRC / "views" / "crm" / "Customers.vue")
    results.append(
        check(
            "V2e-4-2 列表进详情",
            "CustomerDetail" in customers_vue or "/crm/customers/" in customers_vue or "goDetail" in customers_vue,
            "Customers.vue",
        )
    )

    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()
    token = sales_token(SALES_A_PHONE, tenant_id)
    tag = uuid.uuid4().hex[:6]
    code, cust = req(
        "POST",
        "/crm/customers",
        token=token,
        body={"company_name": f"详情客户-{tag}", "mobile": f"139{int(tag, 16) % 100000000:08d}", "status": "潜在"},
    )
    cid = cust.get("id")
    code, contact = req(
        "POST",
        f"/crm/customers/{cid}/contacts",
        token=token,
        body={"name": f"联系人-{tag}", "mobile": "13900001111"},
    )
    results.append(check("V2e-4-3 创建联系人", code == 201, str(code)))
    code, acts = req("POST", "/crm/activities", token=token, body={"customer_id": cid, "activity_type": "other", "content": "客户跟进"})
    results.append(check("V2e-4-3 写客户跟进", code == 201, str(code)))
    code, timeline = req("GET", f"/crm/activities?customer_id={cid}", token=token)
    results.append(check("V2e-4-3 跟进列表", code == 200 and len(timeline) >= 1, str(len(timeline) if isinstance(timeline, list) else timeline)))

    detail = _read(WEB_SRC / "views" / "crm" / "CustomerDetail.vue")
    results.append(
        check(
            "V2e-4-4 详情 Tab",
            ("跟进" in detail and "任务" in detail) and ("联系人" in detail or "listContacts" in detail),
            "CustomerDetail.vue",
        )
    )


def step_2e_5(results: list[bool]) -> None:
    """客户列表 Web：导入/视图/列。"""
    customers = WEB_SRC / "views" / "crm" / "Customers.vue"
    text = _read(customers)
    results.append(check("V2e-5-1 CrmImportDialog", "CrmImportDialog" in text and "customer" in text, "import"))
    results.append(check("V2e-5-2 视图切换", "listViews" in text or "activeViewId" in text, "views"))
    results.append(check("V2e-5-3 列设置", "useEntitySchema" in text and "customer" in text, "schema"))

    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()
    token = sales_token(SALES_A_PHONE, tenant_id)
    tag = uuid.uuid4().hex[:6]
    mobile = f"139{(int(tag, 16) % 100000000 + 77):08d}"
    csv_body = f"公司名称,手机,客户状态\n导入公司-{tag},{mobile},潜在\n"
    code, up = _client_upload(token, "customer", csv_body, f"cust-{tag}.csv")
    results.append(check("V2e-5-4 上传客户导入", code == 201, str(code)))
    job_id = up.get("job_id")
    mapping = {c: c for c in up.get("columns", []) if c in ("公司名称", "手机", "客户状态")}
    if "公司名称" not in mapping:
        mapping = {"公司名称": "company_name", "手机": "mobile", "客户状态": "status"}
    else:
        mapping = {
            "公司名称": "company_name",
            "手机": "mobile",
            "客户状态": "status",
        }
    req(
        "PATCH",
        f"/crm/import/jobs/{job_id}",
        token=token,
        body={"mapping": mapping, "options": {"duplicate_key": "mobile", "on_duplicate": "skip", "default_source": "导入"}},
    )
    req("POST", f"/crm/import/jobs/{job_id}/preview", token=token)
    code, run = req("POST", f"/crm/import/jobs/{job_id}/run", token=token)
    results.append(check("V2e-5-4 客户导入 success", code == 200 and run.get("success_count", 0) >= 1, str(run)))


def step_2e_6(results: list[bool]) -> None:
    """活动详情 + campaign_id 筛线索。"""
    check_files(results, "V2e-6-1", [WEB_SRC / "views" / "crm" / "CampaignDetail.vue"])
    router = _read(WEB_SRC / "router.js")
    results.append(check("V2e-6-1 路由 campaigns/:id", "campaigns/:id" in router, "router"))
    campaigns = _read(WEB_SRC / "views" / "crm" / "Campaigns.vue")
    results.append(check("V2e-6-2 列表进详情", "CampaignDetail" in campaigns or "goDetail" in campaigns, "Campaigns.vue"))

    token = admin_token()
    tag = uuid.uuid4().hex[:6]
    code, camp = req("POST", "/crm/campaigns", token=token, body={"name": f"验收活动-{tag}"})
    camp_id = camp.get("id")
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()
    sales = sales_token(SALES_A_PHONE, tenant_id)
    req(
        "POST",
        "/crm/leads",
        token=sales,
        body=lead_body(
            f"活动线索-{tag}",
            mobile=f"139{(int(tag, 16) % 100000000 + 88):08d}",
            status="待跟进",
            campaign_id=camp_id,
        ),
    )
    code, leads = req("GET", f"/crm/leads?campaign_id={camp_id}", token=sales)
    results.append(check("V2e-6-3 campaign_id 筛选", code == 200, str(code)))
    items = leads.get("items", []) if isinstance(leads, dict) else []
    all_match = bool(items) and all(str(i.get("campaign_id")) == str(camp_id) for i in items)
    results.append(check("V2e-6-3 筛出线索", all_match, f"n={len(items)} camp={camp_id}"))

    detail = _read(WEB_SRC / "views" / "crm" / "CampaignDetail.vue")
    results.append(
        check(
            "V2e-6-4 详情指标",
            "lead_count" in detail or "content_count" in detail,
            "CampaignDetail.vue",
        )
    )


def step_2e_7(results: list[bool]) -> None:
    """分配负责人 API + UI。"""
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
        sales_a = ctx[SALES_A_PHONE]
        sales_b = ctx[SALES_B_PHONE]
    finally:
        db.close()

    sales_token_a = sales_token(SALES_A_PHONE, tenant_id)
    sales_token_b = sales_token(SALES_B_PHONE, tenant_id)
    admin = admin_token()
    tag = uuid.uuid4().hex[:6]
    code, lead = req(
        "POST",
        "/crm/leads",
        token=sales_token_a,
        body=lead_body(
            f"分配-{tag}",
            mobile=f"139{(int(tag, 16) % 100000000 + 55):08d}",
            status="待跟进",
        ),
    )
    lid = lead.get("id")
    code, _ = req("PATCH", f"/crm/leads/{lid}", token=sales_token_a, body={"owner_user_id": sales_b})
    results.append(check("V2e-7-1 sales 无 assign 403", code == 403, str(code)))
    code, patched = req("PATCH", f"/crm/leads/{lid}", token=admin, body={"owner_user_id": sales_b})
    results.append(check("V2e-7-2 admin assign 200", code == 200 and patched.get("owner_user_id") == sales_b, str(patched.get("owner_user_id"))))

    lead_detail = _read(WEB_SRC / "views" / "crm" / "LeadDetail.vue")
    results.append(
        check(
            "V2e-7-3 LeadDetail 分配 UI",
            ("updateLead" in lead_detail or "分配" in lead_detail) and "owner" in lead_detail.lower(),
            "LeadDetail.vue",
        )
    )
    cust_detail = _read(WEB_SRC / "views" / "crm" / "CustomerDetail.vue")
    results.append(
        check(
            "V2e-7-4 CustomerDetail 分配 UI",
            ("updateCustomer" in cust_detail or "分配" in cust_detail) and "owner" in cust_detail.lower(),
            "CustomerDetail.vue",
        )
    )


def step_2e_8(results: list[bool]) -> None:
    """H5 线索详情 + 转化。"""
    check_files(results, "V2e-8-1", [MP_SRC / "pages" / "crm" / "lead-detail.vue"])
    pages = _read(MP_SRC / "pages.json")
    results.append(check("V2e-8-1 pages.json", "crm/lead-detail" in pages, "pages.json"))
    api = _read(MP_SRC / "utils" / "api.js")
    results.append(check("V2e-8-2 getLead", "getLead" in api, "api.js"))
    results.append(check("V2e-8-2 convertLead", "convertLead" in api, "api.js"))
    leads = _read(MP_SRC / "pages" / "crm" / "leads.vue")
    results.append(
        check(
            "V2e-8-3 跳转详情",
            "lead-detail" in leads and ("navigateTo" in leads or "uni.navigateTo" in leads),
            "leads.vue",
        )
    )
    detail = _read(MP_SRC / "pages" / "crm" / "lead-detail.vue")
    tasks_vue = _read(MP_SRC / "components" / "crm" / "CrmEntityTasks.vue")
    combined = detail + tasks_vue
    results.append(
        check(
            "V2e-8-4 跟进任务",
            "createActivity" in combined and "createTask" in combined and "updateTask" in combined,
            "lead-detail + CrmEntityTasks",
        )
    )
    results.append(check("V2e-8-5 转化", "convertLead" in detail and "转化" in detail, "lead-detail.vue"))


STEPS = {
    "2e-1": step_2e_1,
    "2e-2": step_2e_2,
    "2e-3": step_2e_3,
    "2e-4": step_2e_4,
    "2e-5": step_2e_5,
    "2e-6": step_2e_6,
    "2e-7": step_2e_7,
    "2e-8": step_2e_8,
}


def main() -> int:
    args = run_step_parser(list(STEPS.keys()))
    results: list[bool] = []
    if args.step:
        STEPS[args.step](results)
    else:
        for fn in STEPS.values():
            fn(results)
    return finish_phase("2e", results)


if __name__ == "__main__":
    raise SystemExit(main())
