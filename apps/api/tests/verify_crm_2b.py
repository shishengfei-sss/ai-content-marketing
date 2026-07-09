#!/usr/bin/env python3

"""CRM-2b 验收：Schema + 列偏好（docs/v0.5-crm执行计划.md §7）。"""

from __future__ import annotations



import sys

import uuid

from pathlib import Path



API_ROOT = Path(__file__).resolve().parents[1]

WEB_SRC = API_ROOT.parent / "web" / "src"

MP_SRC = API_ROOT.parent / "mp" / "src"

sys.path.insert(0, str(API_ROOT))



from sqlalchemy import inspect



from app.database import SessionLocal, engine

from app.services.crm.schema_seeds import LEAD_LABEL_EXPECTATIONS

from tests.alembic_head import is_at_expected_head

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





def step_2b_1(results: list[bool]) -> None:

    import subprocess



    proc = subprocess.run(

        [sys.executable, "-m", "alembic", "current"],

        cwd=API_ROOT,

        capture_output=True,

        text=True,

    )

    out = proc.stdout + proc.stderr

    results.append(check("V2b-1-0 alembic", is_at_expected_head(out), out.strip()[:80]))

    insp = inspect(engine)

    for table in ("entity_field_definitions", "user_entity_view_preferences"):

        results.append(check(f"V2b-1-1 表 {table}", insp.has_table(table)))





def step_2b_2(results: list[bool]) -> None:

    db = SessionLocal()

    try:

        ensure_crm_test_users(db)

    finally:

        db.close()



    token = sales_token()

    code, schema = req("GET", "/crm/schema/lead", token=token)

    results.append(check("V2b-2-1 GET schema", code == 200, str(code)))

    fields = {f["field_key"]: f for f in schema.get("fields", [])}

    results.append(check("V2b-2-2 种子数量", len(fields) >= 20, str(len(fields))))



    for key, label in LEAD_LABEL_EXPECTATIONS.items():

        got = fields.get(key, {}).get("label")

        results.append(check(f"V2b-2-3 label {key}", got == label, f"{key}={got}"))





def step_2b_3(results: list[bool]) -> None:

    db = SessionLocal()

    try:

        ensure_crm_test_users(db)

    finally:

        db.close()



    admin = admin_token()

    cf_key = f"cf_verify_{uuid.uuid4().hex[:6]}"



    code, _ = req(

        "POST",

        "/crm/schema/lead/fields",

        token=admin,

        body={

            "field_key": cf_key,

            "label": "验收自定义",

            "field_type": "select",

            "options": ["A", "B"],

        },

    )

    results.append(check("V2b-3-1 创建cf字段", code == 201, str(code)))



    code, _ = req(

        "POST",

        "/crm/leads",

        token=sales_token(),

        body=lead_body("校验线索", extra_data={cf_key: "非法值"}),

    )

    results.append(check("V2b-3-2 非法枚举422", code == 422, str(code)))



    code, lead = req(

        "POST",

        "/crm/leads",

        token=sales_token(),

        body=lead_body("校验线索OK", extra_data={cf_key: "A"}),

    )

    results.append(check("V2b-3-3 合法extra_data", code == 201 and lead.get("extra_data", {}).get(cf_key) == "A", str(code)))



    code, _ = req("DELETE", f"/crm/schema/lead/fields/{cf_key}", token=admin)

    results.append(check("V2b-3-4 软删自定义", code == 204, str(code)))





def step_2b_4(results: list[bool]) -> None:

    check_files(

        results,

        "V2b-4-1 Web组件",

        [

            WEB_SRC / "components" / "crm" / "DynamicField.vue",

            WEB_SRC / "views" / "SettingsSchema.vue",

            WEB_SRC / "composables" / "useEntitySchema.js",

        ],

    )

    router_text = (WEB_SRC / "router.js").read_text(encoding="utf-8")

    leads_text = (WEB_SRC / "views" / "crm" / "Leads.vue").read_text(encoding="utf-8")

    results.append(

        check(

            "V2b-4-2 路由与列设置",

            "SettingsSchema" in router_text

            and "crm.schema.manage" in router_text

            and "列设置" in leads_text

            and "useEntitySchema" in leads_text,

            "router/Leads",

        )

    )





def step_2b_5(results: list[bool]) -> None:

    check_files(

        results,

        "V2b-5-1 H5文件",

        [

            MP_SRC / "utils" / "useEntitySchema.js",

            MP_SRC / "pages" / "crm" / "leads.vue",

        ],

    )

    leads_text = (MP_SRC / "pages" / "crm" / "leads.vue").read_text(encoding="utf-8")

    results.append(

        check(

            "V2b-5-2 动态列",

            "useEntitySchema" in leads_text and "列设置" in leads_text,

            "mp/leads.vue",

        )

    )





def step_2b_6(results: list[bool]) -> None:

    db = SessionLocal()

    try:

        ensure_crm_test_users(db)

    finally:

        db.close()



    admin = admin_token()

    token_a = sales_token(SALES_A_PHONE)

    token_b = sales_token(SALES_B_PHONE)



    code, schema = req("GET", "/crm/schema/lead", token=token_a)

    fields = {f["field_key"]: f["label"] for f in schema.get("fields", [])}

    for key, label in LEAD_LABEL_EXPECTATIONS.items():

        results.append(check(f"V2b-6-1 {key}", fields.get(key) == label, fields.get(key)))



    code, _ = req("DELETE", "/crm/schema/lead/fields/company_name", token=admin)

    results.append(check("V2b-6-2 删系统字段403", code == 403, str(code)))



    cols_a = [

        {"field_key": "company_name", "visible": True, "order": 0},

        {"field_key": "mobile", "visible": True, "order": 1},

    ]

    cols_b = [

        {"field_key": "company_name", "visible": True, "order": 0},

        {"field_key": "status", "visible": True, "order": 1},

    ]

    req("PUT", "/me/view-preferences/lead", token=token_a, body={"columns": cols_a})

    req("PUT", "/me/view-preferences/lead", token=token_b, body={"columns": cols_b})



    _, pref_a = req("GET", "/me/view-preferences/lead", token=token_a)

    _, pref_b = req("GET", "/me/view-preferences/lead", token=token_b)

    keys_a = [c["field_key"] for c in pref_a.get("columns", []) if c.get("visible", True)]

    keys_b = [c["field_key"] for c in pref_b.get("columns", []) if c.get("visible", True)]

    results.append(check("V2b-6-3 A含mobile", "mobile" in keys_a, str(keys_a)))

    results.append(check("V2b-6-3 B含status", "status" in keys_b, str(keys_b)))

    results.append(check("V2b-6-3 A/B不同", keys_a != keys_b, f"A={keys_a} B={keys_b}"))





STEPS = {

    "2b-1": step_2b_1,

    "2b-2": step_2b_2,

    "2b-3": step_2b_3,

    "2b-4": step_2b_4,

    "2b-5": step_2b_5,

    "2b-6": step_2b_6,

}





def main() -> int:

    args = run_step_parser(list(STEPS.keys()))

    results: list[bool] = []

    try:

        if args.step:

            STEPS[args.step](results)

        else:

            for key in STEPS:

                STEPS[key](results)

    except Exception as e:

        print(f"ERROR: {e}")

        raise

    return finish_phase("2b", results)





if __name__ == "__main__":

    raise SystemExit(main())

