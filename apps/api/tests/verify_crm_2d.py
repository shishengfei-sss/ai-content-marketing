#!/usr/bin/env python3

"""CRM-2d 验收：数据导入（docs/v0.5-crm执行计划.md §9）。"""

from __future__ import annotations



import io

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

    check,

    check_files,

    ensure_crm_test_users,

    finish_phase,

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





def _client_get_template(token: str, entity_type: str) -> tuple[int, str]:

    from fastapi.testclient import TestClient

    from app.main import app



    client = TestClient(app)

    r = client.get(

        f"/api/v1/crm/import/template/{entity_type}",

        headers={"Authorization": f"Bearer {token}"},

    )

    return r.status_code, r.content.decode("utf-8-sig")





def _build_csv_10_rows(tag: str) -> str:
    base = int(tag[:6], 16) % 100000000
    lines = ["公司名称,联系人,手机,线索状态"]
    for i in range(1, 9):
        mobile = f"139{(base + i):08d}"
        lines.append(f"导入公司{i}-{tag},联系人{i},{mobile},待跟进")
    lines.append(f",缺名-{tag},139{(base + 9):08d},待跟进")
    lines.append(f"坏状态-{tag},联系人10,139{(base + 10):08d},非法状态")
    return "\n".join(lines) + "\n"





def step_2d_1(results: list[bool]) -> None:

    import subprocess



    proc = subprocess.run(

        [sys.executable, "-m", "alembic", "current"],

        cwd=API_ROOT,

        capture_output=True,

        text=True,

    )

    out = proc.stdout + proc.stderr

    results.append(check("V2d-1-0 alembic", is_at_expected_head(out), out.strip()[:80]))

    insp = inspect(engine)

    for table in ("crm_import_jobs", "crm_import_rows"):

        results.append(check(f"V2d-1-1 表 {table}", insp.has_table(table)))





def step_2d_2(results: list[bool]) -> None:

    db = SessionLocal()

    try:

        ensure_crm_test_users(db)

    finally:

        db.close()



    token = sales_token()

    tag = uuid.uuid4().hex[:6]

    csv_text = "公司名称,联系人,手机\n测试公司,张三,13900001111\n"

    code, body = _client_upload(token, "lead", csv_text, f"parse-{tag}.csv")

    results.append(check("V2d-2-1 上传CSV", code == 201, str(code)))

    results.append(check("V2d-2-2 返回列名", "columns" in body and "公司名称" in body.get("columns", []), str(body)))





def step_2d_3(results: list[bool]) -> None:

    token = sales_token()

    code, text = _client_get_template(token, "lead")

    results.append(check("V2d-3-1 模板下载", code == 200, str(code)))

    results.append(check("V2d-3-2 含公司名称", "公司名称" in text, text[:80]))

    results.append(check("V2d-3-3 含手机", "手机" in text, text[:80]))



    check_files(

        results,

        "V2d-3-4 Web导入组件",

        [WEB_SRC / "components" / "crm" / "CrmImportDialog.vue"],

    )

    leads_text = (WEB_SRC / "views" / "crm" / "Leads.vue").read_text(encoding="utf-8")

    results.append(check("V2d-3-5 Leads导入入口", "CrmImportDialog" in leads_text and "导入" in leads_text, "Leads.vue"))





def step_2d_4(results: list[bool]) -> None:

    db = SessionLocal()

    try:

        ctx = ensure_crm_test_users(db)

        sales_user_id = ctx[SALES_A_PHONE]

    finally:

        db.close()



    token = sales_token()

    tag = uuid.uuid4().hex[:6]

    csv_text = _build_csv_10_rows(tag)

    code, upload = _client_upload(token, "lead", csv_text, f"run-{tag}.csv")

    results.append(check("V2d-4-1 创建job", code == 201, str(code)))

    job_id = upload["job_id"]

    mapping = upload.get("suggested_mapping") or {

        "公司名称": "company_name",

        "联系人": "contact_name",

        "手机": "mobile",

        "线索状态": "status",

    }

    code, _ = req("PATCH", f"/crm/import/jobs/{job_id}", token=token, body={"mapping": mapping})

    results.append(check("V2d-4-2 提交mapping", code == 200, str(code)))

    code, preview = req("POST", f"/crm/import/jobs/{job_id}/preview", token=token)

    results.append(check("V2d-4-3 预览", code == 200, str(code)))

    results.append(check("V2d-4-4 预览有错误", preview.get("error_count", 0) >= 2, str(preview)))



    code, job = req("POST", f"/crm/import/jobs/{job_id}/run", token=token)

    results.append(check("V2d-4-5 执行导入", code == 200, str(code)))

    results.append(check("V2d-4-6 success=8", job.get("success_count") == 8, str(job)))

    results.append(check("V2d-4-7 error=2", job.get("error_count") == 2, str(job)))



    code, err_csv = _client_get_errors(token, job_id)

    results.append(check("V2d-4-8 错误CSV", code == 200 and "error_message" in err_csv, err_csv[:60]))



    # owner = 导入人

    code, leads = req("GET", "/crm/leads", token=token)

    imported = [i for i in leads.get("items", []) if f"导入公司1-{tag}" in i.get("company_name", "")]

    results.append(check("V2d-4-9 owner=导入人", len(imported) == 1 and imported[0]["owner_user_id"] == sales_user_id, str(imported)))





def _client_get_errors(token: str, job_id: str) -> tuple[int, str]:

    from fastapi.testclient import TestClient

    from app.main import app



    client = TestClient(app)

    r = client.get(

        f"/api/v1/crm/import/jobs/{job_id}/errors",

        headers={"Authorization": f"Bearer {token}"},

    )

    return r.status_code, r.content.decode("utf-8-sig")





def step_2d_5(results: list[bool]) -> None:

    db = SessionLocal()

    try:

        ctx = ensure_crm_test_users(db)

        sales_user_id = ctx[SALES_A_PHONE]

    finally:

        db.close()



    token = sales_token()

    tag = uuid.uuid4().hex[:6]



    code, tpl = _client_get_template(token, "lead")

    results.append(check("V2d-5-4 模板含公司名称", "公司名称" in tpl, tpl[:100]))

    results.append(check("V2d-5-4 模板含手机", "手机" in tpl, tpl[:100]))



    dup_mobile = f"139{(int(tag, 16) % 100000000 + 99):08d}"

    csv1 = f"公司名称,联系人,手机,线索状态\n重复测-{tag},张三,{dup_mobile},待跟进\n"

    code, up1 = _client_upload(token, "lead", csv1)

    job1 = up1["job_id"]

    mapping = {
        "公司名称": "company_name",
        "联系人": "contact_name",
        "手机": "mobile",
        "线索状态": "status",
    }

    req("PATCH", f"/crm/import/jobs/{job1}", token=token, body={"mapping": mapping})

    code, run1 = req("POST", f"/crm/import/jobs/{job1}/run", token=token)

    results.append(check("V2d-5-2 首次导入", code == 200 and run1.get("success_count") == 1, str(run1)))



    csv2 = f"公司名称,联系人,手机,线索状态\n重复测2-{tag},李四,{dup_mobile},待跟进\n"

    code, up2 = _client_upload(token, "lead", csv2)

    job2 = up2["job_id"]

    req(

        "PATCH",

        f"/crm/import/jobs/{job2}",

        token=token,

        body={"mapping": mapping, "options": {"duplicate_key": "mobile", "on_duplicate": "skip"}},

    )

    code, run2 = req("POST", f"/crm/import/jobs/{job2}/run", token=token)

    results.append(check("V2d-5-2 重复skip", run2.get("skip_count") == 1, str(run2)))



    csv10 = _build_csv_10_rows(tag)

    code, up3 = _client_upload(token, "lead", csv10)

    job3 = up3["job_id"]

    req("PATCH", f"/crm/import/jobs/{job3}", token=token, body={"mapping": mapping})

    code, run3 = req("POST", f"/crm/import/jobs/{job3}/run", token=token)

    results.append(check("V2d-5-1 8成功2失败", run3.get("success_count") == 8 and run3.get("error_count") == 2, str(run3)))



    code, leads = req("GET", "/crm/leads", token=token)

    one = next((i for i in leads.get("items", []) if i.get("company_name") == f"导入公司1-{tag}"), None)

    results.append(check("V2d-5-3 owner=导入人", one and one["owner_user_id"] == sales_user_id, str(one)))





STEPS = {

    "2d-1": step_2d_1,

    "2d-2": step_2d_2,

    "2d-3": step_2d_3,

    "2d-4": step_2d_4,

    "2d-5": step_2d_5,

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

    return finish_phase("2d", results)





if __name__ == "__main__":

    raise SystemExit(main())

