"""C2 验收：ComplianceAgent 合规审查。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from uuid import UUID

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.database import SessionLocal, uuid_eq
from app.models import Content
from app.services.agent.pipelines import PIPELINE_REGISTRY
from tests.http_client import check, req


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def ensure_fake_platform(admin_token: str) -> None:
    req(
        "PATCH",
        "/admin/platform-llm",
        token=admin_token,
        body={
            "provider": "fake",
            "base_url": "http://fake.local",
            "model": "fake-model",
            "api_key": "fake-key",
            "is_active": True,
        },
    )


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


def set_content_body(content_id: str, body: str) -> None:
    db = SessionLocal()
    try:
        row = db.query(Content).filter(uuid_eq(Content.id, UUID(content_id))).first()
        assert row, content_id
        row.body = body
        db.commit()
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []

    out = alembic_head()
    results.append(check("VC2-1 alembic=020(head)", "020" in out and "head" in out.lower(), out.strip()))
    results.append(check("VC2-1 表 agent_compliance_reports", table_exists("agent_compliance_reports")))

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    token = login("13900000099", "test123456")

    code, tools = req("GET", "/agent/tools", token=token)
    tool_names = [t.get("name") for t in (tools or [])]
    results.append(check("VC2-2 注册 check_compliance", code == 200 and "check_compliance" in tool_names))

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
    step_tools = [s.get("tool_name") for s in steps]
    output = json.loads(wf.get("output_json") or "{}") if wf.get("output_json") else {}
    compliance = output.get("compliance") or {}

    expected = [
        "search_knowledge",
        "analyze_pain_points",
        "strategy_proposals",
        "generate_content",
        "optimize_content",
        "check_compliance",
        "review_for_publish",
    ]
    results.append(check("VC2-3 工作流含合规步骤", code == 200 and step_tools == expected, str(step_tools)))
    results.append(
        check(
            "VC2-4 合规 pass",
            wf.get("status") == "completed" and compliance.get("status") == "pass",
            str(compliance.get("status")),
        )
    )

    content_id = output.get("content_id")
    code2, report = req("POST", "/agent/compliance/check", token=token, body={"content_id": content_id})
    results.append(check("VC2-5 API 合规检查", code2 == 200 and report.get("status") == "pass", str(report.get("status"))))

    set_content_body(content_id, "这是一篇缺少免责说明的正文，承诺绝对保证成功。")
    code3, blocked = req("POST", "/agent/compliance/check", token=token, body={"content_id": content_id})
    issues = blocked.get("issues") or []
    results.append(
        check(
            "VC2-6 违规承诺 block",
            code3 == 200 and blocked.get("status") == "block" and any(i.get("severity") == "block" for i in issues),
            str(blocked.get("status")),
        )
    )

    code4, content = req("GET", f"/content/{content_id}", token=token)
    results.append(
        check(
            "VC2-7 不改审核状态",
            code4 == 200 and content.get("status") == "draft",
            str(content.get("status")),
        )
    )

    pipeline_tools = [s.tool_name for s in PIPELINE_REGISTRY.get("content_create", [])]
    results.append(check("VC2-8 无 publish 步骤", "publish_content" not in pipeline_tools, str(pipeline_tools)))

    proc = subprocess.run([sys.executable, "tests/verify_c1.py"], cwd=API_ROOT)
    results.append(check("VC2-9 verify_c1 回归", proc.returncode == 0))

    passed = all(results)
    print("\n=== C2", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
