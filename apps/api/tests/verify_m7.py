"""M7 验收：平台企业管理、转移管理员、删账号保留租户。"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

API_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = API_ROOT.parent / "web" / "src"
sys.path.insert(0, str(API_ROOT))

from app.permissions import SYSTEM_ROLE_ADMIN
from tests.http_client import check, req


def login(phone, password):
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def me(token):
    code, data = req("GET", "/auth/me", token=token)
    assert code == 200, data
    return data


def select_tenant(token, tenant_id):
    code, data = req("POST", "/auth/select-tenant", token=token, body={"tenant_id": tenant_id})
    assert code == 200, data
    return data["access_token"]


def main():
    results = []

    results.append(check("V7 Web AdminTenants.vue", (WEB_ROOT / "views/admin/AdminTenants.vue").is_file()))

    pa_token = login("13800000000", "admin123456")
    code, tenants = req("GET", "/admin/tenants", token=pa_token)
    results.append(check("V7-1 租户列表", code == 200 and tenants.get("total", 0) >= 1))
    if code == 200 and tenants.get("items"):
        item = next((t for t in tenants["items"] if t.get("member_count", 0) > 0), tenants["items"][0])
        results.append(
            check(
                "V7-6 列表字段",
                all(k in item for k in ("member_count", "quota_used", "quota_limit", "industry_code")),
                str(list(item.keys())),
            )
        )
        tenant_id = item["id"]
        code, members = req("GET", f"/admin/tenants/{tenant_id}/members", token=pa_token)
        results.append(
            check(
                "V7-1 成员列表",
                code == 200
                and isinstance(members, list)
                and len(members) > 0
                and all("phone" in m and "role_code" in m for m in members),
            )
        )

    user_token = login("13900000099", "test123456")
    code, _ = req("GET", "/admin/tenants", token=user_token)
    results.append(check("V7-7 非 platform_admin 403", code == 403, str(code)))

    multi_token = login("13900008888", "Test123456")
    me_m = me(multi_token)
    admin_tenant = next((t for t in me_m["tenants"] if t["role_code"] == SYSTEM_ROLE_ADMIN), None)
    editor_tenant = next((t for t in me_m["tenants"] if t["role_code"] == "editor"), None)

    if admin_tenant and editor_tenant:
        tenant_a = admin_tenant["id"]
        tenant_b = editor_tenant["id"]
        token_a = select_tenant(multi_token, tenant_a)
        editor_phone = f"139{uuid4().int % 10**8:08d}"
        req(
            "POST",
            "/team/members",
            token=token_a,
            body={"phone": editor_phone, "display_name": "M7Transfer", "password": "Test123456"},
        )

        code, members_a = req("GET", f"/admin/tenants/{tenant_a}/members", token=pa_token)
        admin_a = next((m for m in members_a if m["role_code"] == SYSTEM_ROLE_ADMIN), None)
        editor_a = next(
            (m for m in members_a if m["role_code"] == "editor" and m["phone"] == editor_phone),
            None,
        )

        if admin_a and editor_a:
            code, _ = req(
                "POST",
                f"/admin/tenants/{tenant_a}/transfer-admin",
                token=pa_token,
                body={"new_admin_user_id": editor_a["user_id"]},
            )
            results.append(check("V7-2 转移 admin", code == 200, str(code)))

            code, members_after = req("GET", f"/admin/tenants/{tenant_a}/members", token=pa_token)
            new_admin = next((m for m in members_after if m["user_id"] == editor_a["user_id"]), None)
            old_admin = next((m for m in members_after if m["user_id"] == admin_a["user_id"]), None)
            results.append(
                check(
                    "V7-2 角色互换",
                    new_admin and old_admin
                    and new_admin["role_code"] == SYSTEM_ROLE_ADMIN
                    and old_admin["role_code"] == "editor",
                )
            )

            old_me = me(select_tenant(multi_token, tenant_a))
            results.append(
                check(
                    "V7-2 原 admin 失去 tenant.manage",
                    "tenant.manage" not in old_me.get("permissions", []),
                    str(old_me.get("permissions")),
                )
            )

            code, _ = req(
                "POST",
                f"/admin/tenants/{tenant_a}/transfer-admin",
                token=pa_token,
                body={"new_admin_user_id": editor_a["user_id"]},
            )
            results.append(check("V7-3 已是 admin 400", code == 400, str(code)))

            fake_id = str(uuid4())
            code, _ = req(
                "POST",
                f"/admin/tenants/{tenant_a}/transfer-admin",
                token=pa_token,
                body={"new_admin_user_id": fake_id},
            )
            results.append(check("V7-3 非成员 404", code == 404, str(code)))

            code, members_b = req("GET", f"/admin/tenants/{tenant_b}/members", token=pa_token)
            member_b = next((m for m in members_b if m["phone"] == "13900008888"), None)
            results.append(
                check(
                    "V7-4 跨租户角色不变",
                    member_b and member_b["role_code"] == "editor",
                    str(member_b),
                )
            )

            req(
                "POST",
                f"/admin/tenants/{tenant_a}/transfer-admin",
                token=pa_token,
                body={"new_admin_user_id": admin_a["user_id"]},
            )
            code, users = req("GET", "/admin/users", token=pa_token)
            temp_user = next((u for u in users if u.get("phone") == editor_phone), None)
            if temp_user:
                req("DELETE", f"/admin/users/{temp_user['id']}", token=pa_token)
        else:
            results.append(check("V7-2 准备 editor 成员", False, str(members_a)))
    else:
        results.append(check("V7-2 多公司测试账号", False, str(me_m.get("tenants"))))

    phone = f"139{uuid4().int % 10**8:08d}"
    code, reg = req(
        "POST",
        "/auth/register",
        body={
            "phone": phone,
            "password": "Test123456",
            "tenant_name": f"M7Del-{phone}",
            "industry_code": "finance",
            "display_name": "M7Del",
        },
    )
    results.append(check("V7-5 注册待删用户", code == 200, str(reg)))
    if code == 200:
        del_token = login(phone, "Test123456")
        del_me = me(del_token)
        del_tenant_id = del_me["tenants"][0]["id"]
        code, gen = req(
            "POST",
            "/content/generate",
            token=del_token,
            body={
                "platform": "wechat",
                "scene": "product",
                "topic": "M7 delete test",
                "llm_source": "tenant",
            },
        )
        content_ok = code in (200, 400, 502)
        code, contents_before = req("GET", "/admin/contents", token=pa_token, body=None)
        code, tenant_before = req("GET", f"/admin/tenants/{del_tenant_id}", token=pa_token)
        code, users = req("GET", "/admin/users", token=pa_token)
        del_user = next((u for u in users if u.get("phone") == phone), None)
        if del_user:
            code, _ = req("DELETE", f"/admin/users/{del_user['id']}", token=pa_token)
            results.append(check("V7-5 删除账号", code == 200, str(code)))
            code, tenant_after = req("GET", f"/admin/tenants/{del_tenant_id}", token=pa_token)
            results.append(check("V7-5 Tenant 仍在", code == 200 and tenant_after.get("id") == del_tenant_id))
            code, login_fail = req("POST", "/auth/login", body={"phone": phone, "password": "Test123456"})
            results.append(check("V7-5 无法登录", code != 200, str(code)))
        else:
            results.append(check("V7-5 找到待删用户", False, phone))

    passed = all(results)
    print("\n=== M7", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
