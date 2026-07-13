#!/usr/bin/env python3

"""CRM M0 验收：权限 Catalog + 五内置角色（docs/v0.5-crm执行计划.md §2）。"""

from __future__ import annotations



import argparse

import subprocess

import sys

from pathlib import Path



API_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(API_ROOT))



from tests.alembic_head import is_at_expected_head
from tests.http_client import check, req



MIN_CRM_PERMISSIONS = 35





def login(phone: str, password: str) -> str:

    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})

    assert code == 200, data

    return data["access_token"]





def step_m0_1(results: list[bool]) -> None:

    from app.permissions import (

        ALL_PERMISSIONS,

        EDITOR_DEFAULT_PERMISSIONS,

        SALES_DEFAULT_PERMISSIONS,

        SALES_MANAGER_DEFAULT_PERMISSIONS,

        MARKETING_DEFAULT_PERMISSIONS,

    )



    crm_perms = [p for p in ALL_PERMISSIONS if p.startswith("crm.")]

    results.append(check("VM0-1-1 CRM权限数量", len(crm_perms) >= MIN_CRM_PERMISSIONS, str(len(crm_perms))))

    results.append(

        check(

            "VM0-1-2 sales含convert",

            "crm.lead.convert" in SALES_DEFAULT_PERMISSIONS,

            "",

        )

    )

    results.append(

        check(

            "VM0-1-3 sales无task.assign",

            "crm.task.assign" not in SALES_DEFAULT_PERMISSIONS

            and "crm.lead.assign" not in SALES_DEFAULT_PERMISSIONS,

        )

    )

    results.append(

        check(

            "VM0-1-4 manager含team+assign",

            "crm.lead.list_team" in SALES_MANAGER_DEFAULT_PERMISSIONS

            and "crm.task.assign" in SALES_MANAGER_DEFAULT_PERMISSIONS,

        )

    )

    results.append(

        check(

            "VM0-1-5 marketing含campaign",

            "crm.campaign.create" in MARKETING_DEFAULT_PERMISSIONS

            and "crm.customer.create" not in MARKETING_DEFAULT_PERMISSIONS,

        )

    )

    results.append(

        check(

            "VM0-1-7 marketing含lead.edit+convert",

            "crm.lead.edit" in MARKETING_DEFAULT_PERMISSIONS

            and "crm.lead.convert" in MARKETING_DEFAULT_PERMISSIONS

            and "crm.customer.list_own" in MARKETING_DEFAULT_PERMISSIONS

            and "crm.customer.view" in MARKETING_DEFAULT_PERMISSIONS,

        )

    )

    crm_in_editor = [p for p in EDITOR_DEFAULT_PERMISSIONS if p.startswith("crm.")]

    results.append(check("VM0-1-6 editor无CRM", len(crm_in_editor) == 0, str(crm_in_editor)))





def step_m0_2(results: list[bool]) -> None:

    from sqlalchemy import text



    from app.database import engine

    from app.permissions import (

        ALL_PERMISSIONS,

        SALES_DEFAULT_PERMISSIONS,

        SYSTEM_ROLE_ADMIN,

        SYSTEM_ROLE_SALES,

    )



    with engine.connect() as conn:

        rows = conn.execute(

            text(

                """

                SELECT tenant_id, COUNT(*) AS c

                FROM tenant_roles

                WHERE is_system = 1

                GROUP BY tenant_id

                """

            )

        ).fetchall()

        if not rows:

            results.append(check("VM0-2-1 每tenant五内置角色", False, "无 tenant_roles 数据"))

            return

        bad = [f"{r[0]}:{r[1]}" for r in rows if r[1] != 5]

        results.append(check("VM0-2-1 每tenant五内置角色", len(bad) == 0, ", ".join(bad) or "ok"))



        admin_perm_count = conn.execute(

            text(

                """

                SELECT COUNT(DISTINCT trp.permission_code)

                FROM tenant_role_permissions trp

                JOIN tenant_roles tr ON tr.id = trp.role_id

                WHERE tr.code = :code AND tr.is_system = 1

                """

            ),

            {"code": SYSTEM_ROLE_ADMIN},

        ).scalar()

        results.append(

            check(

                "VM0-2-2 admin全部权限",

                admin_perm_count == len(ALL_PERMISSIONS),

                f"{admin_perm_count}/{len(ALL_PERMISSIONS)}",

            )

        )



        sales_perms = conn.execute(

            text(

                """

                SELECT DISTINCT trp.permission_code

                FROM tenant_role_permissions trp

                JOIN tenant_roles tr ON tr.id = trp.role_id

                WHERE tr.code = :code AND tr.is_system = 1

                """

            ),

            {"code": SYSTEM_ROLE_SALES},

        ).fetchall()

        sales_set = {r[0] for r in sales_perms}

        results.append(

            check(

                "VM0-2-3 sales默认权限精确",

                sales_set == set(SALES_DEFAULT_PERMISSIONS),

                f"diff={sales_set.symmetric_difference(SALES_DEFAULT_PERMISSIONS)}",

            )

        )





def step_m0_3(results: list[bool]) -> None:

    admin_token = login("13900000099", "test123456")

    multi_token = login("13900008888", "Test123456")

    code, me_m = req("GET", "/auth/me", token=multi_token)

    tenant_b = me_m["tenants"][1]["id"]

    code, sel = req("POST", "/auth/select-tenant", token=multi_token, body={"tenant_id": tenant_b})

    editor_token = sel["access_token"]



    code, roles = req("GET", "/team/roles", token=admin_token)

    editor_role = next((r for r in roles if r.get("code") == "editor"), None) if code == 200 else None

    if editor_role:

        code, _ = req(

            "PATCH",

            f"/team/roles/{editor_role['id']}",

            token=admin_token,

            body={"name": "编辑"},

        )

        results.append(check("VM0-3-1 admin可改内置角色", code == 200, str(code)))

        code, _ = req(

            "PATCH",

            f"/team/roles/{editor_role['id']}",

            token=editor_token,

            body={"name": "编辑2"},

        )

        results.append(check("VM0-3-2 非admin不可改内置角色", code == 403, str(code)))

        code, _ = req("DELETE", f"/team/roles/{editor_role['id']}", token=admin_token)

        results.append(check("VM0-3-3 不可删内置角色", code in (400, 403), str(code)))

    else:

        results.append(check("VM0-3-1 admin可改内置角色", False, "无 editor 角色"))

        results.append(check("VM0-3-2 非admin不可改内置角色", False, "无 editor 角色"))

        results.append(check("VM0-3-3 不可删内置角色", False, "无 editor 角色"))





def step_m0_4(results: list[bool]) -> None:

    proc = subprocess.run(

        [sys.executable, "-m", "alembic", "current"],

        cwd=API_ROOT,

        capture_output=True,

        text=True,

    )

    out = proc.stdout + proc.stderr

    results.append(check("VM0-4-3 alembic含022", is_at_expected_head(out), out.strip()[:120]))



    code, body = req("GET", "/crm/health")

    results.append(check("VM0-4-1 crm health", code == 200 and body.get("status") == "ok", str(body)))





def step_m0_5(results: list[bool]) -> None:

    admin_token = login("13900000099", "test123456")

    code, roles = req("GET", "/team/roles", token=admin_token)

    system_codes = {r["code"] for r in roles if r.get("is_system")} if code == 200 else set()

    expected = {"admin", "editor", "sales", "sales_manager", "marketing"}

    results.append(

        check(

            "VM0-5-2 五内置角色",

            expected.issubset(system_codes),

            str(sorted(system_codes)),

        )

    )

    sales_role = next((r for r in roles if r.get("code") == "sales"), None) if code == 200 else None

    if sales_role:

        perms = set(sales_role.get("permissions") or [])

        results.append(

            check(

                "VM0-5-3 sales含crm.lead.list_own",

                "crm.lead.list_own" in perms,

                str(sorted(p for p in perms if p.startswith("crm."))[:5]),

            )

        )

    else:

        results.append(check("VM0-5-3 sales含crm.lead.list_own", False, "无 sales 角色"))





STEPS = {

    "M0-1": step_m0_1,

    "M0-2": step_m0_2,

    "M0-3": step_m0_3,

    "M0-4": step_m0_4,

    "M0-5": step_m0_5,

}





def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument("--step", choices=list(STEPS.keys()))

    args = parser.parse_args()



    results: list[bool] = []

    try:

        if args.step:

            STEPS[args.step](results)

        else:

            for fn in STEPS.values():

                fn(results)

    except ImportError as e:

        print(f"IMPORT ERROR (尚未完成 M0-1?): {e}")

        return 1

    except Exception as e:

        print(f"ERROR: {e}")

        raise



    passed = all(results) if results else False

    print("\n=== CRM M0", "全部通过" if passed else "存在失败", "===")

    return 0 if passed else 1





if __name__ == "__main__":

    raise SystemExit(main())

