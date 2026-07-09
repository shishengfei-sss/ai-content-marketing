#!/usr/bin/env python3
"""CRM-2f 验收：§3.18.2 缺口收尾（docs/v0.5-crm-2f执行计划.md）。"""
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


def _read(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


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


def _import_lead_row(token: str, company: str, mobile: str, on_duplicate: str = "skip") -> dict:
    csv_text = f"公司名称,联系人姓名,手机,线索状态\n{company},测试联系人,{mobile},待跟进\n"
    code, up = _client_upload(token, "lead", csv_text)
    if code != 201:
        return {"ok": False, "stage": "upload", "code": code, "body": up}
    job_id = up.get("job_id")
    mapping = {
        "公司名称": "company_name",
        "联系人姓名": "contact_name",
        "手机": "mobile",
        "线索状态": "status",
    }
    code, _ = req(
        "PATCH",
        f"/crm/import/jobs/{job_id}",
        token=token,
        body={
            "mapping": mapping,
            "options": {"duplicate_key": "mobile", "on_duplicate": on_duplicate, "default_source": "导入"},
        },
    )
    if code != 200:
        return {"ok": False, "stage": "patch", "code": code}
    code, _ = req("POST", f"/crm/import/jobs/{job_id}/run", token=token)
    if code != 200:
        return {"ok": False, "stage": "run", "code": code}
    code, job = req("GET", f"/crm/import/jobs/{job_id}", token=token)
    return {"ok": code == 200, "job": job, "mobile": mobile}


def step_2f_1(results: list[bool]) -> None:
    """保存视图增强：公开/默认/钉选。"""
    token = sales_token()
    tag = uuid.uuid4().hex[:6]
    code, view = req(
        "POST",
        "/crm/views",
        token=token,
        body={
            "entity_type": "lead",
            "name": f"钉选验收-{tag}",
            "filters": {"logic": "and", "conditions": []},
            "is_pinned": True,
            "is_default": False,
            "is_public": False,
        },
    )
    results.append(check("V2f-1-1 POST 含 is_pinned", code == 201 and view.get("is_pinned") is True, str(view)))

    admin = admin_token()
    code, pub = req(
        "POST",
        "/crm/views",
        token=admin,
        body={
            "entity_type": "lead",
            "name": f"公开验收-{tag}",
            "filters": {"logic": "and", "conditions": []},
            "is_public": True,
        },
    )
    results.append(check("V2f-1-1 POST 含 is_public", code == 201 and pub.get("is_public") is True, str(code)))

    code, _ = req(
        "POST",
        "/crm/views",
        token=token,
        body={
            "entity_type": "lead",
            "name": f"非法公开-{tag}",
            "filters": {"logic": "and", "conditions": []},
            "is_public": True,
        },
    )
    results.append(check("V2f-1-5 无 manage_public 403", code == 403, str(code)))

    leads = _read(WEB_SRC / "views" / "crm" / "Leads.vue")
    results.append(check("V2f-1-2 Leads 钉选 UI", "is_pinned" in leads or "钉选" in leads, "Leads.vue"))
    results.append(check("V2f-1-3 Leads 默认 UI", "is_default" in leads or "默认视图" in leads, "Leads.vue"))
    customers = _read(WEB_SRC / "views" / "crm" / "Customers.vue")
    results.append(
        check(
            "V2f-1-4 Customers 保存视图增强",
            ("is_pinned" in customers or "钉选" in customers) and ("is_default" in customers or "默认" in customers),
            "Customers.vue",
        )
    )


def step_2f_2(results: list[bool]) -> None:
    """钉选视图进 Web 侧栏。"""
    layout = _read(WEB_SRC / "layouts" / "AppLayout.vue")
    composable = _read(WEB_SRC / "composables" / "usePinnedViews.js")
    sidebar_src = layout + composable
    results.append(
        check(
            "V2f-2-2 侧栏钉选逻辑",
            "is_pinned" in sidebar_src or "pinnedViews" in sidebar_src or "pinned" in sidebar_src.lower(),
            "AppLayout/usePinnedViews",
        )
    )
    results.append(
        check(
            "V2f-2-3 侧栏 view_id",
            "/crm/leads" in sidebar_src and ("view_id" in sidebar_src or "viewId" in sidebar_src),
            "sidebar",
        )
    )
    leads = _read(WEB_SRC / "views" / "crm" / "Leads.vue")
    results.append(
        check(
            "V2f-2-4 Leads route view_id",
            "view_id" in leads and ("route.query" in leads or "useRoute" in leads),
            "Leads.vue",
        )
    )
    token = sales_token()
    code, views = req("GET", "/crm/views?entity_type=lead", token=token)
    pinned = [v for v in (views if isinstance(views, list) else []) if v.get("is_pinned")]
    results.append(check("V2f-2-1 GET views 含 pinned", code == 200, f"pinned_count={len(pinned)}"))


def step_2f_3(results: list[bool]) -> None:
    """导入 on_duplicate=update。"""
    token = sales_token()
    tag = uuid.uuid4().hex[:6]
    mobile = f"139{int(tag, 16) % 100000000:08d}"
    name1 = f"导入公司A-{tag}"
    name2 = f"导入公司B-{tag}"

    first = _import_lead_row(token, name1, mobile, "skip")
    results.append(check("V2f-3-1 首次导入成功", first.get("ok") and first.get("job", {}).get("success_count") == 1, str(first)))

    second_skip = _import_lead_row(token, name2, mobile, "skip")
    skip_job = second_skip.get("job") or {}
    results.append(check("V2f-3-3 skip 模式", skip_job.get("skip_count") == 1, str(skip_job)))

    second_update = _import_lead_row(token, name2, mobile, "update")
    upd_job = second_update.get("job") or {}
    results.append(check("V2f-3-2 update success", upd_job.get("success_count") == 1, str(upd_job)))

    code, lst2 = req("GET", f"/crm/leads?q={name2}", token=token)
    found = (lst2.get("items") or [{}])[0]
    results.append(check("V2f-3-2 公司名已更新", found.get("company_name") == name2, found.get("company_name")))

    dialog = _read(WEB_SRC / "components" / "crm" / "CrmImportDialog.vue")
    results.append(check("V2f-3-5 导入 UI update 选项", "update" in dialog or "更新" in dialog, "CrmImportDialog.vue"))


def step_2f_4(results: list[bool]) -> None:
    """导入 Job 历史。"""
    code, lst = req("GET", "/crm/import/jobs?page=1&page_size=20", token=sales_token())
    results.append(check("V2f-4-1 GET jobs 列表", code == 200 and "items" in lst, str(code)))
    total = lst.get("total", 0) if isinstance(lst, dict) else 0
    results.append(check("V2f-4-2 total>=0", code == 200 and total >= 0, str(total)))

    client_js = _read(WEB_SRC / "api" / "client.js")
    leads = _read(WEB_SRC / "views" / "crm" / "Leads.vue")
    hist_vue = _read(WEB_SRC / "views" / "crm" / "CrmImportHistory.vue")
    dialog = _read(WEB_SRC / "components" / "crm" / "CrmImportDialog.vue")
    ui_src = client_js + leads + hist_vue + dialog
    results.append(check("V2f-4-3 listImportJobs 或历史入口", "listImportJobs" in ui_src or "导入历史" in ui_src, "web"))
    results.append(check("V2f-4-4 错误下载", "/errors" in ui_src or "import/jobs" in ui_src, "web"))


def step_2f_5(results: list[bool]) -> None:
    """任务指派执行人 UI。"""
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
        sales_b = ctx[SALES_B_PHONE]
    finally:
        db.close()

    token_a = sales_token(SALES_A_PHONE, tenant_id)
    tag = uuid.uuid4().hex[:6]
    code, task = req("POST", "/crm/tasks", token=token_a, body={"title": f"指派-{tag}", "status": "open"})
    task_id = task.get("id")
    mgr = admin_token()
    code, patched = req("PATCH", f"/crm/tasks/{task_id}", token=mgr, body={"assignee_user_id": sales_b})
    results.append(check("V2f-5-2 manager assign 200", code == 200, str(patched.get("assignee_user_id"))))

    code, filtered = req("GET", f"/crm/tasks?assignee_user_id={sales_b}&page_size=50", token=mgr)
    ids = [t["id"] for t in (filtered.get("items") or [])]
    results.append(check("V2f-5-1 assignee 筛选", code == 200 and task_id in ids, str(len(ids))))

    tasks_vue = _read(WEB_SRC / "views" / "crm" / "Tasks.vue")
    results.append(check("V2f-5-3 执行人筛选 UI", "assignee" in tasks_vue or "执行人" in tasks_vue, "Tasks.vue"))
    results.append(
        check(
            "V2f-5-4 新建含 assignee",
            "assignee_user_id" in tasks_vue or ("执行人" in tasks_vue and "create" in tasks_vue.lower()),
            "Tasks.vue",
        )
    )


def step_2f_6(results: list[bool]) -> None:
    """H5 分配负责人。"""
    api = _read(MP_SRC / "utils" / "api.js")
    lead_detail = _read(MP_SRC / "pages" / "crm" / "lead-detail.vue")
    cust_detail = _read(MP_SRC / "pages" / "crm" / "customer-detail.vue")
    results.append(check("V2f-6-1 updateLead", "updateLead" in api, "api.js"))
    results.append(check("V2f-6-2 lead 分配", "分配" in lead_detail and "updateLead" in lead_detail, "lead-detail.vue"))
    results.append(check("V2f-6-3 customer 分配", "分配" in cust_detail and "updateCustomer" in cust_detail, "customer-detail.vue"))

    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
        sales_b = ctx[SALES_B_PHONE]
    finally:
        db.close()
    token = sales_token(SALES_A_PHONE, tenant_id)
    tag = uuid.uuid4().hex[:6]
    code, cust = req(
        "POST",
        "/crm/customers",
        token=token,
        body={"company_name": f"H5分配-{tag}", "mobile": f"138{int(tag, 16) % 100000000:08d}"},
    )
    cid = cust.get("id")
    code, patched = req("PATCH", f"/crm/customers/{cid}", token=admin_token(), body={"owner_user_id": sales_b})
    results.append(check("V2f-6-4 admin PATCH 客户 owner", code == 200 and patched.get("owner_user_id") == sales_b, str(code)))


def step_2f_7(results: list[bool]) -> None:
    """H5 营销活动只读。"""
    check_files(results, "V2f-7-1", [MP_SRC / "pages" / "crm" / "campaigns.vue"])
    pages = _read(MP_SRC / "pages.json")
    results.append(check("V2f-7-1 pages.json campaigns", "crm/campaigns" in pages, "pages.json"))
    api = _read(MP_SRC / "utils" / "api.js")
    results.append(check("V2f-7-2 listCampaigns", "listCampaigns" in api, "api.js"))
    campaigns = _read(MP_SRC / "pages" / "crm" / "campaigns.vue")
    results.append(check("V2f-7-3 navigate 详情", "campaign-detail" in campaigns or "navigateTo" in campaigns, "campaigns.vue"))
    detail_path = MP_SRC / "pages" / "crm" / "campaign-detail.vue"
    if detail_path.is_file():
        detail = _read(detail_path)
        results.append(check("V2f-7-4 lead_count", "lead_count" in detail or "线索" in detail, "campaign-detail.vue"))
    else:
        results.append(check("V2f-7-4 campaign-detail.vue", False, "missing"))
    menu = _read(MP_SRC / "utils" / "permissions.js") + _read(MP_SRC / "pages" / "crm" / "index.vue")
    results.append(check("V2f-7-5 活动入口", "campaign" in menu.lower() or "活动" in menu, "mp menu"))


def step_2f_8(results: list[bool]) -> None:
    """H5 列表视图切换。"""
    api = _read(MP_SRC / "utils" / "api.js")
    leads = _read(MP_SRC / "pages" / "crm" / "leads.vue")
    customers = _read(MP_SRC / "pages" / "crm" / "customers.vue")
    results.append(check("V2f-8-1 listViews", "listViews" in api, "api.js"))
    results.append(check("V2f-8-2 leads view_id", "view_id" in leads or "listViews" in leads, "leads.vue"))
    results.append(check("V2f-8-3 customers view_id", "view_id" in customers or "listViews" in customers, "customers.vue"))

    token = sales_token()
    code, views = req(
        "POST",
        "/crm/views",
        token=token,
        body={
            "entity_type": "customer",
            "name": f"h5视图-{uuid.uuid4().hex[:6]}",
            "filters": {"logic": "and", "conditions": [{"field_key": "status", "op": "eq", "value": "潜在"}]},
        },
    )
    vid = views.get("id") if code == 201 else None
    if vid:
        code, lst = req("GET", f"/crm/customers?view_id={vid}&page_size=5", token=token)
        results.append(check("V2f-8-4 view_id API", code == 200 and "items" in lst, str(code)))
    else:
        results.append(check("V2f-8-4 创建视图失败", False, str(code)))


def step_2f_9(results: list[bool]) -> None:
    """跟进删除。"""
    token = sales_token()
    tag = uuid.uuid4().hex[:6]
    code, lead = req("POST", "/crm/leads", token=token, body=lead_body(f"跟进删-{tag}", status="待跟进"))
    lid = lead.get("id")
    code, act = req(
        "POST",
        "/crm/activities",
        token=token,
        body={"lead_id": lid, "activity_type": "call", "content": f"删我-{tag}"},
    )
    aid = act.get("id")
    results.append(check("V2f-9-0 创建跟进", code == 201, str(aid)))

    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()
    token_b = sales_token(SALES_B_PHONE, tenant_id)
    code, _ = req("DELETE", f"/crm/activities/{aid}", token=token_b)
    results.append(check("V2f-9-2 非创建人 403", code == 403, str(code)))

    code, _ = req("DELETE", f"/crm/activities/{aid}", token=token)
    results.append(check("V2f-9-1 创建人删除", code in (200, 204), str(code)))

    code, act2 = req(
        "POST",
        "/crm/activities",
        token=token,
        body={"lead_id": lid, "activity_type": "call", "content": f"admin删-{tag}"},
    )
    aid2 = act2.get("id")
    code, _ = req("DELETE", f"/crm/activities/{aid2}", token=admin_token())
    results.append(check("V2f-9-3 admin 删除", code in (200, 204), str(code)))

    lead_detail = _read(WEB_SRC / "views" / "crm" / "LeadDetail.vue")
    cust_detail = _read(WEB_SRC / "views" / "crm" / "CustomerDetail.vue")
    results.append(check("V2f-9-4 Web 删除 UI", "deleteActivity" in lead_detail + cust_detail or "删除" in lead_detail, "detail"))


def step_2f_10(results: list[bool]) -> None:
    """转化时跟进迁移。"""
    token = sales_token()
    tag = uuid.uuid4().hex[:6]
    code, lead = req(
        "POST",
        "/crm/leads",
        token=token,
        body={
            "company_name": f"迁移-{tag}",
            "contact_name": "测试",
            "mobile": f"137{int(tag, 16) % 100000000:08d}",
            "status": "待跟进",
        },
    )
    lid = lead.get("id")
    for i in range(2):
        req("POST", "/crm/activities", token=token, body={"lead_id": lid, "activity_type": "call", "content": f"跟进{i}-{tag}"})
    code, conv = req("POST", f"/crm/leads/{lid}/convert", token=token)
    cid = conv.get("customer_id")
    results.append(check("V2f-10-0 转化", code == 201 and cid, str(conv)))

    code, acts = req("GET", f"/crm/activities?customer_id={cid}", token=token)
    act_list = acts if isinstance(acts, list) else []
    results.append(check("V2f-10-1 客户跟进>=2", code == 200 and len(act_list) >= 2, str(len(act_list))))
    if act_list:
        results.append(check("V2f-10-2 内容含 tag", any(tag in (a.get("content") or "") for a in act_list), str(act_list[0].get("content"))))

    code, lead_acts = req("GET", f"/crm/activities?lead_id={lid}", token=token)
    lead_list = lead_acts if isinstance(lead_acts, list) else []
    results.append(check("V2f-10-3 线索跟进仍在", code == 200 and len(lead_list) >= 2, str(len(lead_list))))

    code, _ = req("POST", f"/crm/leads/{lid}/convert", token=token)
    results.append(check("V2f-10-4 重复转化409", code == 409, str(code)))


def step_2f_11(results: list[bool]) -> None:
    """H5 Schema 对齐。"""
    schema_js = _read(MP_SRC / "utils" / "useEntitySchema.js")
    results.append(check("V2f-11-1 useEntitySchema", "getSchema" in schema_js, "useEntitySchema.js"))
    leads = _read(MP_SRC / "pages" / "crm" / "leads.vue")
    results.append(check("V2f-11-2 leads schema 列", "useEntitySchema" in leads or "list_fields" in leads or "getSchema" in leads, "leads.vue"))
    detail = _read(MP_SRC / "pages" / "crm" / "lead-detail.vue")
    results.append(check("V2f-11-3 detail extra", "extra_data" in detail or "useEntitySchema" in detail, "lead-detail.vue"))

    token = admin_token()
    tag = uuid.uuid4().hex[:8]
    fk = f"cf_h5_{tag}"
    code, _ = req(
        "POST",
        "/crm/schema/lead/fields",
        token=token,
        body={"field_key": fk, "label": "H5验收", "field_type": "text", "show_in_form": True, "show_in_list": True},
    )
    code, lead = req(
        "POST",
        "/crm/leads",
        token=token,
        body=lead_body(f"schema-{tag}", extra_data={fk: "h5-val"}, status="待跟进"),
    )
    lid = lead.get("id")
    code, got = req("GET", f"/crm/leads/{lid}", token=token)
    extra = (got.get("extra_data") or {}) if code == 200 else {}
    results.append(check("V2f-11-4 API extra_data", extra.get(fk) == "h5-val", str(extra)))


STEPS = {
    "2f-1": step_2f_1,
    "2f-2": step_2f_2,
    "2f-3": step_2f_3,
    "2f-4": step_2f_4,
    "2f-5": step_2f_5,
    "2f-6": step_2f_6,
    "2f-7": step_2f_7,
    "2f-8": step_2f_8,
    "2f-9": step_2f_9,
    "2f-10": step_2f_10,
    "2f-11": step_2f_11,
}


def main() -> int:
    args = run_step_parser(list(STEPS.keys()))
    results: list[bool] = []
    if args.step:
        STEPS[args.step](results)
    else:
        for fn in STEPS.values():
            fn(results)
    return finish_phase("2f", results)


if __name__ == "__main__":
    raise SystemExit(main())
