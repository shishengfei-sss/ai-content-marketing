#!/usr/bin/env python3
"""CRM F-2 UAT：需求 §6.2 场景 13～29（API 可自动化部分 + 双端文件门禁）。

Web/H5 全流程点选仍须人工执行；运行 ``--print-manual`` 打印清单。
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = API_ROOT.parent / "web" / "src"
MP_SRC = API_ROOT.parent / "mp" / "src"
sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal
from app.models import TenantMembership, TenantRole, User
from app.permissions import SYSTEM_ROLE_EDITOR, SYSTEM_ROLE_SALES, SYSTEM_ROLE_SALES_MANAGER
from app.services.auth_service import hash_password
from app.services.membership_service import get_membership
from tests.http_client import check, req
from tests.verify_crm_2d import _build_csv_10_rows, _client_get_template, _client_upload
from tests.verify_crm_helpers import (
    SALES_A_PHONE,
    SALES_B_PHONE,
    admin_token,
    check_files,
    editor_token,
    ensure_crm_test_users,
    finish_phase,
    lead_body,
    reset_test_client,
    sales_token,
)

SALES_MGR_PHONE = "13900001003"

MANUAL_UAT_ITEMS = [
    "Web：Dashboard CRM 卡片数字与 /crm/leads、/crm/tasks 快捷入口可点击",
    "Web：线索列表导入向导（模板下载→映射→预览→执行）全流程",
    "Web：客户列表视图切换、列设置、导入与详情 Tab",
    "Web：活动详情概况/线索/任务 Tab；线索详情分配负责人",
    "Web：editor 改 sales 后侧栏出现/隐藏 CRM 菜单（场景 29 UI）",
    "H5：线索列表→详情→写跟进→建任务→标记完成→转化（FR-CLIENT-01）",
    "H5：与 Web 同账号对比 scope（本人线索不可见他人）",
]


def _ensure_sales_manager(db) -> dict[str, str]:
    base = ensure_crm_test_users(db)
    tenant_id = base["tenant_id"]
    mgr_role = (
        db.query(TenantRole)
        .filter(TenantRole.tenant_id == uuid.UUID(tenant_id), TenantRole.code == SYSTEM_ROLE_SALES_MANAGER)
        .first()
    )
    if not mgr_role:
        raise RuntimeError("sales_manager role missing")
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
    user.tenant_id = uuid.UUID(tenant_id)
    membership = get_membership(db, user.id, uuid.UUID(tenant_id))
    if not membership:
        db.add(
            TenantMembership(
                user_id=user.id,
                tenant_id=uuid.UUID(tenant_id),
                role_id=mgr_role.id,
                is_active=True,
            )
        )
    else:
        membership.role_id = mgr_role.id
    db.commit()
    base["manager_user_id"] = str(user.id)
    return base


def _membership_id(db, phone: str, tenant_id: str) -> str:
    m = (
        db.query(TenantMembership)
        .join(User, User.id == TenantMembership.user_id)
        .filter(User.phone == phone, TenantMembership.tenant_id == uuid.UUID(tenant_id))
        .first()
    )
    if not m:
        raise RuntimeError(f"membership not found for {phone}")
    return str(m.id)


def uat_13(results: list[bool]) -> None:
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()

    tag = uuid.uuid4().hex[:6]
    sales_a = sales_token(SALES_A_PHONE, tenant_id)
    sales_b = sales_token(SALES_B_PHONE, tenant_id)
    admin = admin_token()

    code, lead = req(
        "POST",
        "/crm/leads",
        token=sales_a,
        body=lead_body(f"UAT13-{tag}", mobile=f"139{int(tag, 16) % 100000000:08d}"),
    )
    results.append(check("VUAT-13-1 sales 创建线索", code == 201, str(code)))
    lead_id = lead.get("id")

    code, list_b = req("GET", "/crm/leads", token=sales_b)
    ids_b = [x["id"] for x in list_b.get("items", [])] if code == 200 else []
    results.append(check("VUAT-13-2 B 不见 A 线索", lead_id not in ids_b, str(ids_b[:2])))

    code, list_admin = req("GET", "/crm/leads", token=admin)
    ids_admin = [x["id"] for x in list_admin.get("items", [])] if code == 200 else []
    results.append(check("VUAT-13-3 admin 全可见", lead_id in ids_admin, str(len(ids_admin))))


def uat_14(results: list[bool]) -> None:
    admin = admin_token()
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        _ensure_sales_manager(db)
        tenant_id = ctx["tenant_id"]
        a_mid = _membership_id(db, SALES_A_PHONE, tenant_id)
        mgr_mid = _membership_id(db, SALES_MGR_PHONE, tenant_id)
        req(
            "PATCH",
            f"/crm/sales-profiles/{a_mid}",
            token=admin,
            body={"reports_to_membership_id": mgr_mid},
        )
    finally:
        db.close()

    tag = uuid.uuid4().hex[:6]
    sales_a = sales_token(SALES_A_PHONE, tenant_id)
    mgr = sales_token(SALES_MGR_PHONE, tenant_id)
    code, lead = req("POST", "/crm/leads", token=sales_a, body=lead_body(f"UAT14-{tag}"))
    results.append(check("VUAT-14-1 A 建线索", code == 201, str(code)))

    code, listed = req("GET", "/crm/leads", token=mgr)
    ids = [i["id"] for i in listed.get("items", [])]
    results.append(check("VUAT-14-2 manager 见下级", lead["id"] in ids, str(ids[:2])))


def uat_15(results: list[bool]) -> None:
    admin = admin_token()
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        _ensure_sales_manager(db)
        tenant_id = ctx["tenant_id"]
        mgr_mid = _membership_id(db, SALES_MGR_PHONE, tenant_id)
    finally:
        db.close()

    tag = uuid.uuid4().hex[:6]
    code, parent = req("POST", "/crm/territories", token=admin, body={"name": f"UAT东-{tag}", "code": f"e{tag[:4]}"})
    code, child = req(
        "POST",
        "/crm/territories",
        token=admin,
        body={"name": f"UAT沪-{tag}", "code": f"s{tag[:4]}", "parent_id": parent["id"]},
    )
    results.append(check("VUAT-15-1 创建地区树", code == 201 and child.get("parent_id") == parent["id"], str(code)))

    req(
        "PATCH",
        f"/crm/sales-profiles/{mgr_mid}",
        token=admin,
        body={"primary_territory_id": parent["id"]},
    )
    req(
        "PATCH",
        f"/crm/territories/{parent['id']}",
        token=admin,
        body={"manager_membership_id": mgr_mid},
    )
    reset_test_client()

    sales_b = sales_token(SALES_B_PHONE, tenant_id)
    mgr = sales_token(SALES_MGR_PHONE, tenant_id)
    code, lead = req(
        "POST",
        "/crm/leads",
        token=sales_b,
        body=lead_body(f"UAT15-{tag}", territory_id=child["id"]),
    )
    results.append(check("VUAT-15-2 子地区线索", code == 201, str(code)))
    lead_id = lead.get("id")

    code, one = req("GET", f"/crm/leads/{lead_id}", token=mgr)
    results.append(check("VUAT-15-3 地区负责人可见", code == 200, str(code)))


def uat_16(results: list[bool]) -> None:
    admin = admin_token()
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        _ensure_sales_manager(db)
        tenant_id = ctx["tenant_id"]
        a_mid = _membership_id(db, SALES_A_PHONE, tenant_id)
        mgr_mid = _membership_id(db, SALES_MGR_PHONE, tenant_id)
        req("PATCH", f"/crm/sales-profiles/{a_mid}", token=admin, body={"reports_to_membership_id": mgr_mid})
    finally:
        db.close()

    tag = uuid.uuid4().hex[:6]
    sales_a = sales_token(SALES_A_PHONE, tenant_id)
    mgr = sales_token(SALES_MGR_PHONE, tenant_id)
    code, lead = req("POST", "/crm/leads", token=sales_a, body=lead_body(f"UAT16-{tag}"))
    lead_id = lead["id"]

    content = f"跟进记录-{tag}"
    code, _ = req(
        "POST",
        "/crm/activities",
        token=sales_a,
        body={"lead_id": lead_id, "activity_type": "call", "content": content},
    )
    results.append(check("VUAT-16-1 写跟进", code == 201, str(code)))

    code, timeline = req("GET", f"/crm/activities?lead_id={lead_id}", token=sales_a)
    results.append(
        check(
            "VUAT-16-2 A 时间线",
            code == 200 and any(content in (a.get("content") or "") for a in timeline),
            str(timeline)[:80],
        )
    )

    code, mgr_tl = req("GET", f"/crm/activities?lead_id={lead_id}", token=mgr)
    results.append(
        check(
            "VUAT-16-3 manager 可见跟进",
            code == 200 and any(content in (a.get("content") or "") for a in mgr_tl),
            str(code),
        )
    )


def uat_17_18(results: list[bool]) -> None:
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()

    tag = uuid.uuid4().hex[:6]
    sales_a = sales_token(SALES_A_PHONE, tenant_id)
    code, lead = req(
        "POST",
        "/crm/leads",
        token=sales_a,
        body=lead_body(f"UAT17-{tag}", contact_name="张经理", mobile=f"138{int(tag, 16) % 100000000:08d}"),
    )
    code, conv = req("POST", f"/crm/leads/{lead['id']}/convert", token=sales_a)
    results.append(check("VUAT-17-1 转化 201", code == 201, str(code)))
    customer_id = conv.get("customer_id")

    code, lead_after = req("GET", f"/crm/leads/{lead['id']}", token=sales_a)
    results.append(check("VUAT-17-2 线索已转化", lead_after.get("status") == "已转化", lead_after.get("status")))

    code, contact = req(
        "POST",
        f"/crm/customers/{customer_id}/contacts",
        token=sales_a,
        body={"name": "李助理", "mobile": "13900001234", "is_primary": False},
    )
    results.append(check("VUAT-18-1 增联系人", code == 201, str(code)))

    code, contacts = req("GET", f"/crm/customers/{customer_id}/contacts", token=sales_a)
    names = [c.get("name") for c in contacts] if code == 200 else []
    results.append(check("VUAT-18-2 联系人列表", "李助理" in names, str(names)))


def uat_19(results: list[bool]) -> None:
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()

    sales_a = sales_token(SALES_A_PHONE, tenant_id)
    code, before = req("GET", "/dashboard/stats", token=sales_a)
    due_before = before.get("crm_tasks_due_today", 0)

    today_end = datetime.combine(date.today(), datetime.max.time()).replace(tzinfo=timezone.utc)
    code, task = req(
        "POST",
        "/crm/tasks",
        token=sales_a,
        body={"title": f"UAT19-{uuid.uuid4().hex[:6]}", "due_at": today_end.isoformat()},
    )
    results.append(check("VUAT-19-1 创建今日任务", code == 201, str(code)))

    code, after = req("GET", "/dashboard/stats", token=sales_a)
    due_after = after.get("crm_tasks_due_today", 0)
    results.append(check("VUAT-19-2 今日待办+1", due_after >= due_before + 1, f"{due_before}->{due_after}"))

    code, done = req("PATCH", f"/crm/tasks/{task['id']}", token=sales_a, body={"status": "done"})
    results.append(check("VUAT-19-3 任务完成", code == 200 and done.get("status") == "done", str(done.get("status"))))


def uat_20_21(results: list[bool]) -> None:
    admin = admin_token()
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()

    cf_key = f"cf_tax_id_{uuid.uuid4().hex[:4]}"
    code, field = req(
        "POST",
        "/crm/schema/lead/fields",
        token=admin,
        body={"field_key": cf_key, "label": "税号", "field_type": "text"},
    )
    results.append(check("VUAT-20-1 自定义字段", code == 201, str(code)))

    token_a = sales_token(SALES_A_PHONE, tenant_id)
    token_b = sales_token(SALES_B_PHONE, tenant_id)
    code, schema = req("GET", "/crm/schema/lead", token=token_a)
    keys = {f["field_key"] for f in schema.get("fields", [])}
    results.append(check("VUAT-20-2 schema 含字段", cf_key in keys, str(cf_key in keys)))

    cols_a = [{"field_key": "company_name", "visible": True, "order": 0}, {"field_key": "mobile", "visible": True, "order": 1}]
    cols_b = [{"field_key": "company_name", "visible": True, "order": 0}, {"field_key": "status", "visible": True, "order": 1}]
    req("PUT", "/me/view-preferences/lead", token=token_a, body={"columns": cols_a})
    req("PUT", "/me/view-preferences/lead", token=token_b, body={"columns": cols_b})
    _, pref_a = req("GET", "/me/view-preferences/lead", token=token_a)
    _, pref_b = req("GET", "/me/view-preferences/lead", token=token_b)
    keys_a = [c["field_key"] for c in pref_a.get("columns", []) if c.get("visible")]
    keys_b = [c["field_key"] for c in pref_b.get("columns", []) if c.get("visible")]
    results.append(check("VUAT-21-1 A/B 列偏好不同", keys_a != keys_b, f"A={keys_a} B={keys_b}"))

    req("DELETE", f"/crm/schema/lead/fields/{cf_key}", token=admin)


def uat_22(results: list[bool]) -> None:
    from tests.verify_crm_2a import MARKETING_PHONE, _ensure_marketing_user, marketing_token

    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        _ensure_marketing_user(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()

    mkt = marketing_token()
    tag = uuid.uuid4().hex[:6]
    code, camp = req("POST", "/crm/campaigns", token=mkt, body={"name": f"UAT22-{tag}", "status": "active"})
    camp_id = camp["id"]

    sales_a = sales_token(SALES_A_PHONE, tenant_id)
    code, lead = req(
        "POST",
        "/crm/leads",
        token=sales_a,
        body=lead_body(f"UAT22L-{tag}", campaign_id=camp_id),
    )
    results.append(check("VUAT-22-1 活动线索", code == 201, str(code)))

    code, detail = req("GET", f"/crm/campaigns/{camp_id}", token=mkt)
    results.append(check("VUAT-22-2 lead_count>=1", detail.get("lead_count", 0) >= 1, str(detail.get("lead_count"))))

    code, filtered = req("GET", f"/crm/leads?campaign_id={camp_id}", token=sales_a)
    n = len(filtered.get("items", [])) if code == 200 else 0
    results.append(check("VUAT-22-3 campaign_id 筛选", n >= 1, f"n={n}"))


def uat_23_24(results: list[bool]) -> None:
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        tenant_id = ctx["tenant_id"]
    finally:
        db.close()

    tag = uuid.uuid4().hex[:6]
    token_a = sales_token(SALES_A_PHONE, tenant_id)
    editor = editor_token()

    req("POST", "/crm/leads", token=token_a, body=lead_body(f"UAT23A-{tag}", status="跟进中"))
    req("POST", "/crm/leads", token=token_a, body=lead_body(f"UAT23B-{tag}", status="待跟进"))

    code, view = req(
        "POST",
        "/crm/views",
        token=token_a,
        body={
            "entity_type": "lead",
            "name": f"我跟进中-{tag}",
            "filters": {"logic": "and", "conditions": [{"field_key": "status", "op": "eq", "value": "跟进中"}]},
        },
    )
    view_id = view["id"]
    code, filtered = req("GET", f"/crm/leads?view_id={view_id}", token=token_a)
    names = [i.get("company_name") for i in filtered.get("items", [])]
    results.append(check("VUAT-23-1 私有视图筛选", f"UAT23A-{tag}" in names and f"UAT23B-{tag}" not in names, str(names[:2])))

    admin = admin_token()
    code, pub = req(
        "POST",
        "/crm/views",
        token=admin,
        body={
            "entity_type": "lead",
            "name": f"公开本月-{tag}",
            "is_public": True,
            "filters": {"logic": "and", "conditions": [{"field_key": "company_name", "op": "contains", "value": tag}]},
        },
    )
    results.append(check("VUAT-24-1 公开视图", code == 201, str(code)))

    code, ed_list = req("GET", f"/crm/leads?view_id={pub['id']}", token=editor)
    ed_names = [i.get("company_name") for i in ed_list.get("items", [])] if code == 200 else []
    results.append(check("VUAT-24-2 editor 仍仅本人 scope", len(ed_names) == 0, str(ed_names)))


def uat_25_27(results: list[bool]) -> None:
    db = SessionLocal()
    try:
        ctx = ensure_crm_test_users(db)
        sales_user_id = ctx[SALES_A_PHONE]
    finally:
        db.close()

    token = sales_token()
    tag = uuid.uuid4().hex[:6]
    admin = admin_token()
    cf_key = f"cf_tax_{uuid.uuid4().hex[:4]}"
    req(
        "POST",
        "/crm/schema/lead/fields",
        token=admin,
        body={"field_key": cf_key, "label": "税号导入", "field_type": "text"},
    )

    code, tpl = _client_get_template(token, "lead")
    results.append(check("VUAT-25-1 模板含公司名称", "公司名称" in tpl and "手机" in tpl, tpl[:60]))

    csv10 = _build_csv_10_rows(tag)
    code, upload = _client_upload(token, "lead", csv10, f"uat-{tag}.csv")
    job_id = upload["job_id"]
    mapping = {
        "公司名称": "company_name",
        "联系人": "contact_name",
        "联系人姓名": "contact_name",
        "手机": "mobile",
        "线索状态": "status",
    }
    req("PATCH", f"/crm/import/jobs/{job_id}", token=token, body={"mapping": mapping})
    code, preview = req("POST", f"/crm/import/jobs/{job_id}/preview", token=token)
    results.append(check("VUAT-25-2 预览 2 行错误", preview.get("error_count", 0) >= 2, str(preview.get("error_count"))))

    code, job = req("POST", f"/crm/import/jobs/{job_id}/run", token=token)
    results.append(check("VUAT-25-3 8 行成功", job.get("success_count") == 8, str(job)))

    dup_mobile = f"139{(int(tag, 16) % 100000000 + 77):08d}"
    csv_dup = f"公司名称,联系人姓名,手机,线索状态\n重复-{tag},测试联系人,{dup_mobile},待跟进\n"
    _, up1 = _client_upload(token, "lead", csv_dup)
    req("PATCH", f"/crm/import/jobs/{up1['job_id']}", token=token, body={"mapping": mapping})
    req("POST", f"/crm/import/jobs/{up1['job_id']}/run", token=token)
    _, up2 = _client_upload(token, "lead", csv_dup)
    req(
        "PATCH",
        f"/crm/import/jobs/{up2['job_id']}",
        token=token,
        body={"mapping": mapping, "options": {"duplicate_key": "mobile", "on_duplicate": "skip"}},
    )
    _, run2 = req("POST", f"/crm/import/jobs/{up2['job_id']}/run", token=token)
    results.append(check("VUAT-26-1 重复 skip", run2.get("skip_count") == 1, str(run2)))

    tax_val = f"TAX{tag}"
    csv_cf = f"公司名称,联系人姓名,手机,{cf_key}\n税号测-{tag},测试联系人,139{(int(tag, 16) % 100000000 + 88):08d},{tax_val}\n"
    _, up3 = _client_upload(token, "lead", csv_cf)
    req("PATCH", f"/crm/import/jobs/{up3['job_id']}", token=token, body={"mapping": {"公司名称": "company_name", "联系人姓名": "contact_name", "手机": "mobile", cf_key: cf_key}})
    req("POST", f"/crm/import/jobs/{up3['job_id']}/run", token=token)
    code, leads = req("GET", "/crm/leads", token=token)
    one = next((i for i in leads.get("items", []) if i.get("company_name") == f"税号测-{tag}"), None)
    extra = (one or {}).get("extra_data") or {}
    results.append(check("VUAT-27-1 extra_data 税号", extra.get(cf_key) == tax_val, str(extra)))

    code, owned = req("GET", "/crm/leads", token=token)
    imported = [i for i in owned.get("items", []) if f"导入公司1-{tag}" in (i.get("company_name") or "")]
    results.append(check("VUAT-25-4 owner=导入人", len(imported) == 1 and imported[0]["owner_user_id"] == sales_user_id, str(imported[:1])))

    req("DELETE", f"/crm/schema/lead/fields/{cf_key}", token=admin)


def uat_28_29(results: list[bool]) -> None:
    admin = admin_token()
    code, roles = req("GET", "/team/roles", token=admin)
    system_codes = {r["code"] for r in roles if r.get("is_system")} if code == 200 else set()
    expected = {"admin", "editor", "sales", "sales_manager", "marketing"}
    results.append(check("VUAT-28-1 五内置角色", expected.issubset(system_codes), str(sorted(system_codes))))

    sales_role = next((r for r in roles if r.get("code") == SYSTEM_ROLE_SALES), None)
    editor_role = next((r for r in roles if r.get("code") == SYSTEM_ROLE_EDITOR), None)
    if sales_role:
        perms = set(sales_role.get("permissions") or [])
        results.append(check("VUAT-28-2 sales 含 list_own", "crm.lead.list_own" in perms, str(sorted(p for p in perms if p.startswith("crm."))[:3])))
    mgr_role = next((r for r in roles if r.get("code") == SYSTEM_ROLE_SALES_MANAGER), None)
    if mgr_role:
        mgr_perms = set(mgr_role.get("permissions") or [])
        results.append(check("VUAT-28-3 sales_manager 含 list_team", "crm.lead.list_team" in mgr_perms, str(sorted(p for p in mgr_perms if "list_" in p)[:4])))
    if sales_role and editor_role:
        db = SessionLocal()
        try:
            tenant_id = ensure_crm_test_users(db)["tenant_id"]
        finally:
            db.close()
        reset_test_client()

        admin = admin_token()
        code, members = req("GET", "/team/members", token=admin)
        b_row = next((m for m in members if m.get("phone") == SALES_B_PHONE), None) if code == 200 else None
        results.append(check("VUAT-29-0 找到成员 B", b_row is not None and b_row.get("role_code") == "sales", str(b_row)))
        if not b_row:
            return

        sales_b = sales_token(SALES_B_PHONE, tenant_id)
        code, me_sales = req("GET", "/auth/me", token=sales_b)
        crm_perms = [p for p in (me_sales.get("permissions") or []) if p.startswith("crm.")]
        results.append(check("VUAT-28-4 sales 用户有 CRM", "crm.lead.list_own" in crm_perms, str(crm_perms[:3])))

        code, patched = req(
            "PATCH",
            f"/team/members/{b_row['id']}/role",
            token=admin,
            body={"role_id": editor_role["id"]},
        )
        results.append(check("VUAT-29-1a 改 editor", code == 200, str(code)))
        reset_test_client()
        sales_b = sales_token(SALES_B_PHONE, tenant_id)
        code, me_ed = req("GET", "/auth/me", token=sales_b)
        ed_crm = [p for p in (me_ed.get("permissions") or []) if p.startswith("crm.")]
        results.append(check("VUAT-29-1 editor 无 CRM 权限", len(ed_crm) == 0, str(ed_crm)))

        sales_role_id = b_row["role_id"]
        code, patched_back = req(
            "PATCH",
            f"/team/members/{b_row['id']}/role",
            token=admin,
            body={"role_id": sales_role_id},
        )
        results.append(
            check(
                "VUAT-29-2a 改回 sales",
                code == 200 and str(patched_back.get("role_id")) == str(sales_role_id),
                str(patched_back),
            )
        )
        reset_test_client()
        sales_b = sales_token(SALES_B_PHONE, tenant_id)
        code, me_back = req("GET", "/auth/me", token=sales_b)
        back_crm = [p for p in (me_back.get("permissions") or []) if p.startswith("crm.")]
        results.append(check("VUAT-29-2 改回 sales 有 CRM", "crm.lead.list_own" in back_crm, str(back_crm[:3])))

        nav_web = (WEB_SRC / "config" / "permissions.js").read_text(encoding="utf-8")
        results.append(check("VUAT-29-3 Web NAV 权限门控", "permissionAny" in nav_web and "/crm/leads" in nav_web, "permissions.js"))
        nav_mp = (MP_SRC / "utils" / "permissions.js").read_text(encoding="utf-8")
        results.append(check("VUAT-29-4 H5 NAV 权限门控", "permissionAny" in nav_mp, "mp permissions.js"))


def uat_dual_end_files(results: list[bool]) -> None:
    check_files(
        results,
        "VUAT-M-WEB",
        [
            WEB_SRC / "views" / "Dashboard.vue",
            WEB_SRC / "views" / "crm" / "Leads.vue",
            WEB_SRC / "views" / "crm" / "LeadDetail.vue",
            WEB_SRC / "views" / "crm" / "Customers.vue",
            WEB_SRC / "views" / "crm" / "CustomerDetail.vue",
            WEB_SRC / "views" / "crm" / "CampaignDetail.vue",
        ],
    )
    check_files(
        results,
        "VUAT-M-H5",
        [
            MP_SRC / "pages" / "crm" / "leads.vue",
            MP_SRC / "pages" / "crm" / "lead-detail.vue",
            MP_SRC / "pages" / "crm" / "tasks.vue",
        ],
    )


STEPS = {
    "13": uat_13,
    "14": uat_14,
    "15": uat_15,
    "16": uat_16,
    "17-18": uat_17_18,
    "19": uat_19,
    "20-21": uat_20_21,
    "22": uat_22,
    "23-24": uat_23_24,
    "25-27": uat_25_27,
    "28-29": uat_28_29,
    "files": uat_dual_end_files,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=list(STEPS.keys()), help="单场景验收，如 13、25-27")
    parser.add_argument("--print-manual", action="store_true", help="打印须人工点测的 Web/H5 项")
    args = parser.parse_args()

    if args.print_manual:
        print("\n=== F-2 人工 UAT 清单（Web + H5 各测一遍）===\n")
        for i, item in enumerate(MANUAL_UAT_ITEMS, 1):
            print(f"  {i}. {item}")
        print()
        return 0

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
    passed = finish_phase("F-2-API", results)
    if passed == 0:
        print("\n提示：运行 python tests/verify_crm_uat_f2.py --print-manual 查看须人工点测项")
    return passed


if __name__ == "__main__":
    raise SystemExit(main())
