#!/usr/bin/env python3

"""CRM-2c 验收：保存列表视图（docs/v0.5-crm执行计划.md §8）。"""

from __future__ import annotations



import sys

import uuid

from pathlib import Path



API_ROOT = Path(__file__).resolve().parents[1]

WEB_SRC = API_ROOT.parent / "web" / "src"

sys.path.insert(0, str(API_ROOT))



from sqlalchemy import inspect



from app.database import SessionLocal, engine

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





def step_2c_1(results: list[bool]) -> None:

    import subprocess



    proc = subprocess.run(

        [sys.executable, "-m", "alembic", "current"],

        cwd=API_ROOT,

        capture_output=True,

        text=True,

    )

    out = proc.stdout + proc.stderr

    results.append(check("V2c-1-0 alembic", is_at_expected_head(out), out.strip()[:80]))

    insp = inspect(engine)

    results.append(check("V2c-1-1 表 entity_list_views", insp.has_table("entity_list_views")))





def step_2c_2(results: list[bool]) -> None:

    db = SessionLocal()

    try:

        ensure_crm_test_users(db)

    finally:

        db.close()



    token = sales_token()

    code, view = req(

        "POST",

        "/crm/views",

        token=token,

        body={

            "entity_type": "lead",

            "name": f"跟进中-{uuid.uuid4().hex[:6]}",

            "filters": {

                "logic": "and",

                "conditions": [{"field_key": "status", "op": "eq", "value": "跟进中"}],

            },

        },

    )

    results.append(check("V2c-2-1 创建视图", code == 201, str(code)))

    results.append(check("V2c-2-2 视图ID", "id" in view, str(view.get("id"))))



    code, listed = req("GET", "/crm/views?entity_type=lead", token=token)

    results.append(check("V2c-2-3 列表含视图", code == 200 and any(v["id"] == view["id"] for v in listed), str(len(listed))))





def step_2c_3(results: list[bool]) -> None:

    db = SessionLocal()

    try:

        ctx = ensure_crm_test_users(db)

        tenant_id = ctx["tenant_id"]

    finally:

        db.close()



    token_a = sales_token(SALES_A_PHONE)

    tag = uuid.uuid4().hex[:6]



    req(

        "POST",

        "/crm/leads",

        token=token_a,

        body=lead_body(f"视图测A-{tag}", status="跟进中"),

    )

    req(

        "POST",

        "/crm/leads",

        token=token_a,

        body=lead_body(f"视图测B-{tag}", status="待跟进"),

    )



    code, view = req(

        "POST",

        "/crm/views",

        token=token_a,

        body={

            "entity_type": "lead",

            "name": f"仅跟进中-{tag}",

            "filters": {

                "logic": "and",

                "conditions": [{"field_key": "status", "op": "eq", "value": "跟进中"}],

            },

        },

    )

    view_id = view["id"]



    code, all_leads = req("GET", "/crm/leads", token=token_a)

    code, filtered = req("GET", f"/crm/leads?view_id={view_id}", token=token_a)

    results.append(check("V2c-3-1 view_id筛选", code == 200, str(code)))

    results.append(

        check(

            "V2c-3-2 筛选后更少",

            filtered.get("total", 0) <= all_leads.get("total", 0),

            f"{filtered.get('total')} vs {all_leads.get('total')}",

        )

    )

    results.append(

        check(

            "V2c-3-3 均为跟进中",

            all(i.get("status") == "跟进中" for i in filtered.get("items", [])),

            str([i.get("status") for i in filtered.get("items", [])[:3]]),

        )

    )

    results.append(check("V2c-3-4 返回view_id", filtered.get("view_id") == view_id, str(filtered.get("view_id"))))





def step_2c_4(results: list[bool]) -> None:

    leads_text = (WEB_SRC / "views" / "crm" / "Leads.vue").read_text(encoding="utf-8")

    client_text = (WEB_SRC / "api" / "client.js").read_text(encoding="utf-8")

    results.append(

        check(

            "V2c-4-1 Leads视图切换",

            "listViews" in client_text

            and "activeViewId" in leads_text

            and "保存视图" in leads_text,

            "Leads.vue/client.js",

        )

    )

    check_files(results, "V2c-4-2 view_service", [API_ROOT / "app" / "services" / "crm" / "view_service.py"])





def step_2c_5(results: list[bool]) -> None:

    db = SessionLocal()

    try:

        ensure_crm_test_users(db)

    finally:

        db.close()



    token_a = sales_token(SALES_A_PHONE)

    token_b = sales_token(SALES_B_PHONE)

    admin = admin_token()

    tag = uuid.uuid4().hex[:6]



    req("POST", "/crm/leads", token=token_a, body=lead_body(f"V5A-{tag}", status="跟进中"))

    req("POST", "/crm/leads", token=token_a, body=lead_body(f"V5B-{tag}", status="待跟进"))



    code, view = req(

        "POST",

        "/crm/views",

        token=token_a,

        body={

            "entity_type": "lead",

            "name": f"跟进视图-{tag}",

            "filters": {

                "logic": "and",

                "conditions": [{"field_key": "status", "op": "eq", "value": "跟进中"}],

            },

        },

    )

    view_id = view["id"]

    code, filtered = req("GET", f"/crm/leads?view_id={view_id}", token=token_a)

    results.append(check("V2c-5-1 跟进中视图", code == 200 and filtered.get("total", 0) >= 1, str(filtered)))

    results.append(

        check(

            "V2c-5-1 全部跟进中",

            all(i.get("status") == "跟进中" for i in filtered.get("items", [])),

            "status check",

        )

    )



    code, pub_view = req(

        "POST",

        "/crm/views",

        token=admin,

        body={

            "entity_type": "lead",

            "name": f"公开-{tag}",

            "is_public": True,

            "filters": {

                "logic": "and",

                "conditions": [{"field_key": "status", "op": "eq", "value": "跟进中"}],

            },

        },

    )

    pub_id = pub_view["id"]

    code, b_views = req("GET", "/crm/views?entity_type=lead", token=token_b)

    results.append(

        check(

            "V2c-5-2 B可见公开视图",

            any(v["id"] == pub_id for v in b_views),

            str([v["name"] for v in b_views[:5]]),

        )

    )

    code, b_list = req("GET", f"/crm/leads?view_id={pub_id}", token=token_b)

    results.append(check("V2c-5-2 B可用公开视图", code == 200, str(code)))



    cf_key = f"cf_view_{uuid.uuid4().hex[:6]}"

    req(

        "POST",

        f"/crm/schema/lead/fields",

        token=admin,

        body={

            "field_key": cf_key,

            "label": "验收等级",

            "field_type": "select",

            "options": ["高", "低"],

        },

    )

    req(

        "POST",

        "/crm/leads",

        token=token_a,

        body=lead_body(f"CF高-{tag}", status="跟进中", extra_data={cf_key: "高"}),

    )

    req(

        "POST",

        "/crm/leads",

        token=token_a,

        body=lead_body(f"CF低-{tag}", status="跟进中", extra_data={cf_key: "低"}),

    )

    code, cf_view = req(

        "POST",

        "/crm/views",

        token=token_a,

        body={

            "entity_type": "lead",

            "name": f"CF筛选-{tag}",

            "filters": {

                "logic": "and",

                "conditions": [{"field_key": cf_key, "op": "eq", "value": "高"}],

            },

        },

    )

    cf_view_id = cf_view["id"]

    code, cf_filtered = req("GET", f"/crm/leads?view_id={cf_view_id}", token=token_a)

    results.append(check("V2c-5-3 cf筛选", code == 200, str(code)))

    results.append(

        check(

            "V2c-5-3 仅高等级",

            all(

                (i.get("extra_data") or {}).get(cf_key) == "高"

                for i in cf_filtered.get("items", [])

                if (i.get("extra_data") or {}).get(cf_key) is not None

            )

            and cf_filtered.get("total", 0) >= 1,

            str(cf_filtered.get("total")),

        )

    )





STEPS = {

    "2c-1": step_2c_1,

    "2c-2": step_2c_2,

    "2c-3": step_2c_3,

    "2c-4": step_2c_4,

    "2c-5": step_2c_5,

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

    return finish_phase("2c", results)





if __name__ == "__main__":

    raise SystemExit(main())

