"""WF2 验收：Web 创作页接 content_propose / resume 工作流。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_CREATE = API_ROOT.parent / "web" / "src" / "views" / "Create.vue"
WEB_CLIENT = API_ROOT.parent / "web" / "src" / "api" / "client.js"
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req, ensure_fake_platform


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    results: list[bool] = []

    web_vue = WEB_CREATE.read_text(encoding="utf-8") if WEB_CREATE.is_file() else ""
    client_js = WEB_CLIENT.read_text(encoding="utf-8") if WEB_CLIENT.is_file() else ""

    results.append(
        check(
            "VWF2-1 client createWorkflow/resumeWorkflow",
            "createWorkflow" in client_js and "resumeWorkflow" in client_js,
            "client.js",
        )
    )
    results.append(
        check(
            "VWF2-2 Create.vue content_propose",
            "content_propose" in web_vue and "runProposeWorkflow" in web_vue,
            "Create.vue",
        )
    )
    results.append(
        check(
            "VWF2-3 Create.vue resume 选方案",
            "runFinishWorkflow" in web_vue and "workflowId" in web_vue,
            "Create.vue",
        )
    )

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    token = login("13900000099", "test123456")

    code, quota = req("GET", "/settings/llm/quota", token=token)
    used_before = quota.get("used_count", 0) if code == 200 else 0

    code, session = req(
        "POST",
        "/agent/sessions",
        token=token,
        body={"industry_code": "finance", "title": "WF2 E2E"},
    )
    sid = session.get("id") if code == 200 else None

    code, wf = req(
        "POST",
        "/agent/workflows",
        token=token,
        body={
            "pipeline_code": "content_propose",
            "auto_run": True,
            "session_id": sid,
            "input": {
                "platform": "wechat",
                "topic": "税务规范",
                "scene": "bookkeeping_intro",
                "content_format": "article",
                "industry_code": "finance",
                "llm_source": "platform",
            },
        },
    )
    output = json.loads(wf.get("output_json") or "{}") if wf.get("output_json") else {}
    results.append(
        check(
            "VWF2-4 API propose 暂停",
            code == 200 and wf.get("status") == "paused" and len(output.get("proposals") or []) >= 3,
            wf.get("status"),
        )
    )

    wf_id = wf.get("id")
    if wf_id:
        code2, wf2 = req(
            "POST",
            f"/agent/workflows/{wf_id}/resume",
            token=token,
            body={"selected_proposal_index": 0},
        )
        output2 = json.loads(wf2.get("output_json") or "{}") if wf2.get("output_json") else {}
        results.append(
            check(
                "VWF2-5 API resume 完成",
                code2 == 200 and wf2.get("status") == "completed" and bool(output2.get("content_id")),
                wf2.get("status"),
            )
        )
        if output2.get("content_id"):
            code3, content = req("GET", f"/content/{output2['content_id']}", token=token)
            results.append(
                check(
                    "VWF2-6 正文可 GET",
                    code3 == 200 and bool(content.get("body")),
                    str(code3),
                )
            )

        code4, quota2 = req("GET", "/settings/llm/quota", token=token)
        used_after = quota2.get("used_count", 0) if code4 == 200 else used_before
        results.append(
            check(
                "VWF2-7 generate 扣额度",
                used_after == used_before + 1,
                f"{used_before}->{used_after}",
            )
        )

    proc = subprocess.run([sys.executable, "tests/verify_wf_ui.py"], cwd=API_ROOT)
    results.append(check("VWF2-8 回归 verify_wf_ui", proc.returncode == 0, str(proc.returncode)))

    failed = [i for i, ok in enumerate(results) if not ok]
    if failed:
        print(f"\n=== WF2 失败 {len(failed)}/{len(results)} ===")
        return 1
    print("\n=== WF2 全部通过 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
