"""M8 总验收：发布门禁、§6.1～6.3 UAT（API + 双端文件 + README）。"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
WEB_ROOT = API_ROOT.parent / "web" / "src"
MP_ROOT = API_ROOT.parent / "mp" / "src"
README = REPO_ROOT / "README.md"
sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal
from app.permissions import EDITOR_DEFAULT_PERMISSIONS, SYSTEM_ROLE_ADMIN
from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from tests.http_client import check, req
from tests.test_helpers import ensure_multi_tenant_user, restore_single_company_user

WEB_UAT_FILES = [
    "views/SelectTenant.vue",
    "views/ForgotPassword.vue",
    "views/SettingsTenant.vue",
    "views/SettingsTeam.vue",
    "views/admin/AdminTenants.vue",
    "config/permissions.js",
]

MP_UAT_FILES = [
    "pages/select-tenant/select-tenant.vue",
    "pages/forgot/forgot.vue",
    "pages/settings/tenant.vue",
    "pages/settings/team.vue",
    "pages/settings/preference.vue",
    "utils/session.js",
    "utils/permissions.js",
]


def login(phone, password):
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    if code != 200:
        return None, data
    return data["access_token"], data


def select_tenant(token, tenant_id):
    code, data = req("POST", "/auth/select-tenant", token=token, body={"tenant_id": tenant_id})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []

    db = SessionLocal()
    try:
        restore_single_company_user(db)
        ensure_multi_tenant_user(db, "13900008888", "Test123456")
    finally:
        db.close()

    # 发布门禁：README
    readme_text = README.read_text(encoding="utf-8") if README.is_file() else ""
    results.append(check("G8 README 存在", README.is_file()))
    results.append(check("G8 README 含 1111", "1111" in readme_text))
    results.append(check("G8 README 含 platform_admin", "13800000000" in readme_text))
    results.append(check("G8 README 含自动验收", "run_m0_m8" in readme_text or "verify_m8" in readme_text))

    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    results.append(check(f"G8 alembic head={EXPECTED_HEAD}", is_at_expected_head(out), out.strip()))

    for f in WEB_UAT_FILES:
        results.append(check(f"G8 Web {f}", (WEB_ROOT / f).is_file()))
    for f in MP_UAT_FILES:
        results.append(check(f"G8 H5 {f}", (MP_ROOT / f).is_file()))

    pa_token, _ = login("13800000000", "admin123456")
    admin_token, _ = login("13900000099", "test123456")
    if not admin_token:
        req(
            "POST",
            "/auth/register",
            body={
                "phone": "13900000099",
                "password": "test123456",
                "tenant_name": "单公司UAT",
                "industry_code": "finance",
                "display_name": "单公司",
            },
        )
        admin_token, _ = login("13900000099", "test123456")
    multi_token, multi_login = login("13900008888", "Test123456")
    me_m: dict = {}
    editor_tenant = None

    # §6.1 #1 editor 权限
    if multi_token and multi_login:
        code, me_m = req("GET", "/auth/me", token=multi_token)
        editor_tenant = next((t for t in me_m.get("tenants", []) if t["role_code"] == "editor"), None)
        if editor_tenant:
            ed_token = select_tenant(multi_token, editor_tenant["id"])
            code, me_e = req("GET", "/auth/me", token=ed_token)
            perms = sorted(me_e.get("permissions", []))
            results.append(
                check(
                    "UAT-1 editor 默认权限",
                    code == 200 and perms == sorted(EDITOR_DEFAULT_PERMISSIONS),
                    str(perms),
                )
            )
            results.append(
                check(
                    "UAT-1 无 tenant.manage",
                    "tenant.manage" not in perms and "team.role.manage" not in perms,
                )
            )

    # §6.1 #2 多公司选公司与隔离
    if multi_token:
        results.append(check("UAT-2 need_select", multi_login.get("need_select_tenant") is True))
        me_m = req("GET", "/auth/me", token=multi_token)[1]
        if len(me_m.get("tenants", [])) >= 2:
            token_a = select_tenant(multi_token, me_m["tenants"][0]["id"])
            token_b = select_tenant(multi_token, me_m["tenants"][1]["id"])
            _, list_a = req("GET", "/content", token=token_a)
            _, list_b = req("GET", "/content", token=token_b)
            ids_a = {i["id"] for i in list_a.get("items", [])}
            ids_b = {i["id"] for i in list_b.get("items", [])}
            results.append(check("UAT-2 租户内容隔离", ids_a.isdisjoint(ids_b) or (not ids_a and not ids_b)))

    # §6.1 #4 admin 改企业 / editor 403
    if admin_token:
        code, _ = req("PATCH", "/tenant/profile", token=admin_token, body={"name": "甲公司UAT"})
        results.append(check("UAT-4 admin 改公司名", code == 200, str(code)))
    if multi_token and editor_tenant:
        ed_token = select_tenant(multi_token, editor_tenant["id"])
        code, _ = req("PATCH", "/tenant/profile", token=ed_token, body={"name": "x"})
        results.append(check("UAT-4 editor 无企业信息", code == 403, str(code)))

    # 公司名全平台唯一
    unique_name = f"UAT-Unique-{uuid4().hex[:8]}"
    reg_phone_a = f"139{uuid4().int % 10**8:08d}"
    reg_phone_b = f"139{uuid4().int % 10**8:08d}"
    code, _ = req(
        "POST",
        "/auth/register",
        body={
            "phone": reg_phone_a,
            "password": "Test123456",
            "tenant_name": unique_name,
            "industry_code": "finance",
        },
    )
    results.append(check("UAT-9 注册带公司名", code == 200, str(code)))
    code, dup = req(
        "POST",
        "/auth/register",
        body={
            "phone": reg_phone_b,
            "password": "Test123456",
            "tenant_name": unique_name,
            "industry_code": "finance",
        },
    )
    results.append(check("UAT-9 重复公司名拒绝", code == 400, str(dup.get("detail", dup))))
    token_a, _ = login(reg_phone_a, "Test123456")
    if token_a:
        code, conflict = req(
            "PATCH",
            "/tenant/profile",
            token=token_a,
            body={"name": "平台管理"},
        )
        results.append(check("UAT-9 改名冲突", code == 400, str(conflict.get("detail", conflict))))

    # §6.1 #5 偏好全局
    if multi_token and len(me_m.get("tenants", [])) >= 2:
        token_a = select_tenant(multi_token, me_m["tenants"][0]["id"])
        marker = f"M8-pref-{uuid4().hex[:8]}"
        req("PUT", "/settings/user-prompt", token=token_a, body={"global_instructions": marker})
        token_b = select_tenant(multi_token, me_m["tenants"][1]["id"])
        code, pref = req("GET", "/settings/user-prompt", token=token_b)
        results.append(check("UAT-5 偏好跨公司相同", code == 200 and pref.get("global_instructions") == marker))

    # §6.1 #6 admin >= editor 看板
    if admin_token and multi_token and editor_tenant:
        ed_token = select_tenant(multi_token, editor_tenant["id"])
        _, admin_dash = req("GET", "/dashboard/stats", token=admin_token)
        _, editor_dash = req("GET", "/dashboard/stats", token=ed_token)
        results.append(
            check(
                "UAT-6 admin>=editor看板",
                admin_dash.get("generated_this_month", 0) >= editor_dash.get("generated_this_month", 0),
            )
        )

    # §6.1 #7/#8 忘记密码
    fp_phone = f"139{uuid4().int % 10**8:08d}"
    req(
        "POST",
        "/auth/register",
        body={"phone": fp_phone, "password": "Test123456", "tenant_name": f"M8FP-{fp_phone}", "industry_code": "finance", "display_name": "M8FP"},
    )
    code, _ = req("POST", "/auth/password/forgot/send-code", body={"phone": fp_phone})
    results.append(check("UAT-7 forgot send-code", code == 200, str(code)))
    code, _ = req(
        "POST",
        "/auth/password/forgot/reset",
        body={"phone": fp_phone, "code": "1111", "password": "NewPass123456"},
    )
    results.append(check("UAT-7 reset 1111", code == 200, str(code)))
    code, _ = req("POST", "/auth/login", body={"phone": fp_phone, "password": "NewPass123456"})
    results.append(check("UAT-7 新密码登录", code == 200, str(code)))

    unknown = f"139{uuid4().int % 10**8:08d}"
    code, body = req("POST", "/auth/password/forgot/send-code", body={"phone": unknown})
    results.append(check("UAT-8 未注册手机号", code in (400, 404), str(body)[:80]))

    # §6.2 #10-12 平台后台
    if pa_token:
        code, tenants = req("GET", "/admin/tenants", token=pa_token)
        results.append(check("UAT-10 企业管理列表", code == 200 and tenants.get("total", 0) >= 1))
        item = next((t for t in tenants.get("items", []) if t.get("member_count", 0) > 0), None)
        if item:
            code, members = req("GET", f"/admin/tenants/{item['id']}/members", token=pa_token)
            results.append(
                check(
                    "UAT-10 成员含手机号角色",
                    code == 200 and members and all("phone" in m and "role_code" in m for m in members),
                )
            )
        code, users = req("GET", "/admin/users", token=pa_token)
        multi_user = next((u for u in users if u.get("phone") == "13900008888"), None)
        results.append(
            check(
                "UAT-12 Membership 展示",
                multi_user and len(multi_user.get("memberships", [])) >= 2,
                str(multi_user),
            )
        )

    # §6.3 MVP 清单（API 可验证项）
    results.append(check("MVP 平台额度 API", admin_token and req("GET", "/settings/llm/quota", token=admin_token)[0] == 200))
    results.append(check("MVP 一人两公司", multi_token and len(me_m.get("tenants", [])) >= 2))
    results.append(check("MVP 企业管理 API", pa_token and req("GET", "/admin/tenants", token=pa_token)[0] == 200))
    results.append(check("MVP 账号管理 API", pa_token and req("GET", "/admin/users", token=pa_token)[0] == 200))
    code, _ = req("POST", "/content/00000000-0000-0000-0000-000000000001/submit-review", token=admin_token or "", body={})
    results.append(check("MVP 审核废止410", code == 410, str(code)))

    # NFR 抽检：列表 API
    if admin_token:
        started = time.perf_counter()
        code, _ = req("GET", "/content", token=admin_token)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        results.append(check("NFR 列表API<2s", code == 200 and elapsed_ms < 2000, f"{elapsed_ms}ms"))

    passed = all(results)
    print("\n=== M8", "全部通过 — v0.3.3 发布门禁 OK" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
