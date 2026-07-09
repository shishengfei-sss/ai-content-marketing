"""C1 验收：WorkflowManager + content_create pipeline。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal
from app.services.agent.pipelines import PIPELINE_REGISTRY
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


def table_exists(table: str) -> bool:
    from sqlalchemy import inspect

    db = SessionLocal()
    try:
        return table in inspect(db.bind).get_table_names()
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []

    out = alembic_head()
    results.append(check("VC1-1 alembic=022(head)", is_at_expected_head(out), out.strip()))
    results.append(check("VC1-1 表 agent_workflows", table_exists("agent_workflows")))
    results.append(check("VC1-1 表 agent_workflow_steps", table_exists("agent_workflow_steps")))

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    token = login("13900000099", "test123456")

    code, pipelines = req("GET", "/agent/pipelines", token=token)
    results.append(
        check(
            "VC1-2 注册 content_create",
            code == 200 and "content_create" in (pipelines.get("pipelines") or []),
            str(pipelines),
        )
    )

    code, quota = req("GET", "/settings/llm/quota", token=token)
    used_before = quota.get("used_count", 0)

    code, wf = req(
        "POST",
        "/agent/workflows",
        token=token,
        body={
            "pipeline_code": "content_create",
            "auto_run": True,
            "input": {
                "platform": "wechat",
                "topic": "报税提醒",
                "scene": "bookkeeping_intro",
                "content_format": "article",
                "industry_code": "finance",
                "llm_source": "platform",
                "search_query": "报税",
            },
        },
    )
    steps = wf.get("steps") or []
    tool_names = [s.get("tool_name") for s in steps]
    output = json.loads(wf.get("output_json") or "{}") if wf.get("output_json") else {}

    expected_tools = [
        "search_knowledge",
        "analyze_pain_points",
        "strategy_proposals",
        "generate_content",
        "optimize_content",
        "check_compliance",
        "review_for_publish",
    ]
    results.append(check("VC1-3 工作流 completed", code == 200 and wf.get("status") == "completed", wf.get("status")))
    results.append(
        check(
            "VC1-3 七步 pipeline",
            len(steps) == 7
            and tool_names == expected_tools
            and all(s.get("status") == "completed" for s in steps),
            str(tool_names),
        )
    )
    results.append(
        check(
            "VC1-4 产出 content_id",
            bool(output.get("content_id")),
            str(output.get("content_id", ""))[:40],
        )
    )
    results.append(
        check(
            "VC1-4 含痛点分析与选题理由",
            bool(output.get("pain_analysis")) and bool(output.get("selection_rationale")),
            str(output.get("selection_rationale", ""))[:40],
        )
    )
    results.append(
        check(
            "VC1-4 含合规结果",
            (output.get("compliance") or {}).get("status") == "pass",
            str((output.get("compliance") or {}).get("status")),
        )
    )
    pipeline_tools = [s.tool_name for s in PIPELINE_REGISTRY.get("content_create", [])]
    results.append(
        check(
            "VC1-5 无 publish 步骤",
            "publish_content" not in tool_names and "publish_content" not in pipeline_tools,
            str(tool_names),
        )
    )

    code2, quota2 = req("GET", "/settings/llm/quota", token=token)
    results.append(
        check(
            "VC1-6 generate 扣 1 次额度",
            quota2.get("used_count") == used_before + 1,
            f"{used_before}->{quota2.get('used_count')}",
        )
    )

    proc = subprocess.run([sys.executable, "tests/verify_lm5.py"], cwd=API_ROOT)
    results.append(check("VC1-7 verify_lm5 回归", proc.returncode == 0))

    passed = all(results)
    print("\n=== C1", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
