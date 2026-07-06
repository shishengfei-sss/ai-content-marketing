"""M4 验收：scope 过滤与审核废止。"""
from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req


def login(phone, password):
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main():
    results = []
    admin_token = login("13900000099", "test123456")
    editor_token = login("13900008888", "Test123456")
    code, me = req("GET", "/auth/me", token=editor_token)
    tenant_b = me["tenants"][1]["id"]
    code, sel = req("POST", "/auth/select-tenant", token=editor_token, body={"tenant_id": tenant_b})
    editor_token = sel["access_token"]

    code, admin_dash = req("GET", "/dashboard/stats", token=admin_token)
    code, editor_dash = req("GET", "/dashboard/stats", token=editor_token)
    results.append(check("V4-1 看板可访问", code == 200 and admin_dash and editor_dash))
    results.append(
        check(
            "V4-1 admin>=editor统计",
            admin_dash.get("generated_this_month", 0) >= editor_dash.get("generated_this_month", 0),
            f"admin={admin_dash.get('generated_this_month')} editor={editor_dash.get('generated_this_month')}",
        )
    )

    code, admin_list = req("GET", "/content", token=admin_token)
    code, editor_list = req("GET", "/content", token=editor_token)
    results.append(check("V4-3 内容列表", code == 200))
    if admin_list.get("total", 0) > 0 and editor_list.get("total", 0) >= 0:
        results.append(
            check(
                "V4-3 editor列表<=admin",
                editor_list.get("total", 0) <= admin_list.get("total", 0),
                f"admin={admin_list.get('total')} editor={editor_list.get('total')}",
            )
        )

    if admin_list.get("items"):
        other_id = admin_list["items"][0]["id"]
        code, _ = req("GET", f"/content/{other_id}", token=editor_token)
        results.append(check("V4-4 他人详情不可见", code in (403, 404), str(code)))

    code, _ = req("POST", "/content/00000000-0000-0000-0000-000000000001/submit-review", token=admin_token, body={})
    results.append(check("V4-5 审核410", code == 410, str(code)))

    passed = all(results)
    print("\n=== M4", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
