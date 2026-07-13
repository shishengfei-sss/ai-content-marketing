"""WF1 验收：content_propose 暂停 + resume 跑 content_finish。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import is_at_expected_head
from tests.http_client import check, req, ensure_fake_platform


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def alembic_head() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def main() -> int:
    results: list[bool] = []

    out = alembic_head()
    results.append(check("VWF1-0 alembic=022(head)", is_at_expected_head(out), out.strip()))

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    token = login("13900000099", "test123456")

    code, pipelines = req("GET", "/agent/pipelines", token=token)
    pipe_list = pipelines.get("pipelines") or []
    results.append(
        check(
            "VWF1-1 注册 content_propose/finish",
            code == 200
            and "content_propose" in pipe_list
            and "content_finish" in pipe_list
            and "content_create" in pipe_list,
            str(pipe_list),
        )
    )

    code, quota = req("GET", "/settings/llm/quota", token=token)
    used_before = quota.get("used_count", 0) if code == 200 else 0

    code, wf = req(
        "POST",
        "/agent/workflows",
        token=token,
        body={
            "pipeline_code": "content_propose",
            "auto_run": True,
            "input": {
                "platform": "wechat",
                "topic": "报税提醒",
                "scene": "brand_intro",
                "content_format": "article",
                "industry_code": "marketing",
                "llm_source": "platform",
                "search_query": "报税",
            },
        },
    )
    steps = wf.get("steps") or []
    propose_tools = [s.get("tool_name") for s in steps if s.get("step_index", 99) < 10]
    output = json.loads(wf.get("output_json") or "{}") if wf.get("output_json") else {}

    results.append(
        check(
            "VWF1-2 propose 暂停",
            code == 200 and wf.get("status") == "paused",
            wf.get("status"),
        )
    )
    results.append(
        check(
            "VWF1-2 propose 三步",
            propose_tools
            == ["search_knowledge", "analyze_pain_points", "generate_proposals"]
            and all(s.get("status") == "completed" for s in steps if s.get("step_index", 99) < 3),
            str(propose_tools),
        )
    )
    results.append(
        check(
            "VWF1-3 产出 proposals",
            len(output.get("proposals") or []) >= 3,
            str(len(output.get("proposals") or [])),
        )
    )
    results.append(
        check(
            "VWF1-3 phase=awaiting_selection",
            output.get("phase") == "awaiting_selection",
            output.get("phase"),
        )
    )

    wf_id = wf.get("id")
    if wf_id:
        code_run_paused, _ = req("POST", f"/agent/workflows/{wf_id}/run", token=token)
        results.append(
            check(
                "VWF1-4 paused 不可 run",
                code_run_paused == 400,
                str(code_run_paused),
            )
        )

        code, wf2 = req(
            "POST",
            f"/agent/workflows/{wf_id}/resume",
            token=token,
            body={"selected_proposal_index": 0},
        )
        steps2 = wf2.get("steps") or []
        finish_tools = [
            s.get("tool_name")
            for s in steps2
            if s.get("tool_name")
            in (
                "generate_content",
                "optimize_content",
                "check_compliance",
                "review_for_publish",
            )
        ]
        output2 = json.loads(wf2.get("output_json") or "{}") if wf2.get("output_json") else {}

        results.append(
            check(
                "VWF1-5 resume completed",
                code == 200 and wf2.get("status") == "completed",
                wf2.get("status"),
            )
        )
        results.append(
            check(
                "VWF1-5 finish 四步",
                finish_tools
                == [
                    "generate_content",
                    "optimize_content",
                    "check_compliance",
                    "review_for_publish",
                ],
                str(finish_tools),
            )
        )
        results.append(
            check(
                "VWF1-6 产出 content_id",
                bool(output2.get("content_id")),
                str(output2.get("content_id", ""))[:40],
            )
        )

        code, quota2 = req("GET", "/settings/llm/quota", token=token)
        used_after = quota2.get("used_count", 0) if code == 200 else used_before
        results.append(
            check(
                "VWF1-7 generate 扣 1 次额度",
                used_after == used_before + 1,
                f"{used_before}->{used_after}",
            )
        )

    proc = subprocess.run([sys.executable, "-B", "tests/verify_c1.py"], cwd=API_ROOT)
    results.append(check("VWF1-8 回归 verify_c1", proc.returncode == 0, str(proc.returncode)))

    failed = [i for i, ok in enumerate(results) if not ok]
    if failed:
        print(f"\n=== WF1 失败 {len(failed)}/{len(results)} ===")
        return 1
    print("\n=== WF1 全部通过 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
