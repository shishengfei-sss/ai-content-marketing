"""M3 验收：权限引擎、团队与企业 API。"""
from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.permissions import EDITOR_DEFAULT_PERMISSIONS
from tests.http_client import check, req


def login(phone, password):
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main():
    results = []
    admin_token = login("13900000099", "test123456")
    code, me = req("GET", "/auth/me", token=admin_token)
    results.append(check("V3-1 admin permissions", code == 200 and len(me.get("permissions", [])) == 24))

    multi_token = login("13900008888", "Test123456")
    code, me_m = req("GET", "/auth/me", token=multi_token)
    tenant_b = me_m["tenants"][1]["id"]
    code, sel = req("POST", "/auth/select-tenant", token=multi_token, body={"tenant_id": tenant_b})
    editor_token = sel["access_token"]
    code, me_e = req("GET", "/auth/me", token=editor_token)
    results.append(
        check(
            "V3-1 editor permissions",
            code == 200 and sorted(me_e.get("permissions", [])) == sorted(EDITOR_DEFAULT_PERMISSIONS),
            str(me_e.get("permissions")),
        )
    )

    code, body = req("PATCH", "/tenant/profile", token=editor_token, body={"name": "x"})
    results.append(check("V3-2 editor无tenant.manage", code == 403, str(code)))

    code, role = req(
        "POST",
        "/team/roles",
        token=admin_token,
        body={
            "name": "运营",
            "permissions": ["team.member.manage", "dashboard.view_all", "team.member.view"],
        },
    )
    results.append(check("V3-3 创建自定义角色", code == 200, str(body)[:120]))
    custom_role_id = role.get("id") if code == 200 else None

    code, members = req("GET", "/team/members", token=admin_token)
    results.append(check("V3-5 admin列成员需team.member.view", code == 200, str(code)))

    code, _ = req("PATCH", "/tenant/profile", token=admin_token, body={"credit_code": "123"})
    results.append(check("V3-6 非法信用代码", code == 422))

    code, prof = req(
        "PATCH",
        "/tenant/profile",
        token=admin_token,
        body={"credit_code": "91110000MA01234567"},
    )
    results.append(check("V3-6 合法信用代码", code == 200, str(prof.get("credit_code") if isinstance(prof, dict) else prof)))

    code, roles = req("GET", "/team/roles", token=admin_token)
    results.append(check("V3-3 admin角色列表", code == 200 and len(roles) >= 2))

    if custom_role_id and code == 200 and isinstance(members, list):
        admin_role = next((r for r in roles if r.get("code") == "admin"), None)
        if admin_role and members:
            target = next((m for m in members if m["role_code"] != "admin"), members[0])
            code, _ = req(
                "PATCH",
                f"/team/members/{target['id']}/role",
                token=admin_token,
                body={"role_id": admin_role["id"]},
            )
            # assign admin role by admin - should work; test FR-TEAM-10 with custom role user needs separate setup

    passed = all(results)
    print("\n=== M3", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
