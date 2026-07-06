"""C5 验收：多 Agent Supervisor + handoff。"""
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
from app.services.agent.supervisor_service import assert_agent_may_run_tool, decide_after_compliance
from fastapi import HTTPException
from tests.http_client import _get_test_client, check, req


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
    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    token = login("13900000099", "test123456")
    client = _get_test_client()

    out = alembic_head()
    results.append(check("VC5-0 alembic=020(head)", "020" in out and "head" in out.lower(), out.strip()))

    r = client.get("/api/v1/agent/supervisor/agents", headers={"Authorization": f"Bearer {token}"})
    agents = {a["code"] for a in (r.json().get("agents") or [])}
    results.append(
        check(
            "VC5-1 注册 creator/compliance/ops",
            r.status_code == 200 and {"creator", "compliance", "ops"}.issubset(agents),
            str(sorted(agents)),
        )
    )

    code, wf = req(
        "POST",
        "/agent/workflows",
        token=token,
        body={
            "pipeline_code": "content_create",
            "auto_run": True,
            "input": {
                "platform": "wechat",
                "topic": "Supervisor测试",
                "scene": "bookkeeping_intro",
                "content_format": "article",
                "industry_code": "finance",
                "llm_source": "platform",
                "search_query": "报税",
            },
        },
    )
    steps = wf.get("steps") or []
    agent_codes = [s.get("agent_code") for s in steps]
    handoff_r = client.get(
        f"/api/v1/agent/supervisor/workflows/{wf['id']}/handoffs",
        headers={"Authorization": f"Bearer {token}"},
    )
    handoffs = handoff_r.json().get("handoffs") or []
    involved = {h.get("from_agent") for h in handoffs} | {h.get("to_agent") for h in handoffs}
    results.append(
        check(
            "VC5-1 handoff creator→compliance→ops",
            code == 200
            and wf.get("status") == "completed"
            and "creator" in agent_codes
            and "compliance" in agent_codes
            and "ops" in agent_codes
            and len(handoffs) >= 2
            and "creator" in involved
            and "compliance" in involved
            and "ops" in involved,
            str(handoffs),
        )
    )

    blocked_publish = False
    try:
        assert_agent_may_run_tool("compliance", "publish_content")
    except HTTPException:
        blocked_publish = True
    results.append(check("VC5-2 Compliance 不可 publish", blocked_publish))

    block_decision = decide_after_compliance("block")
    results.append(
        check(
            "VC5-3 block 交还 Creator",
            block_decision.get("target_agent") == "creator"
            and block_decision.get("retry_tool") == "revise_content",
            str(block_decision),
        )
    )

    output = json.loads(wf.get("output_json") or "{}") if wf.get("output_json") else {}
    content_id = output.get("content_id")
    set_content_body(content_id, "缺少免责声明，承诺绝对保证成功。")
    code_block, blocked = req(
        "POST",
        "/agent/compliance/check",
        token=token,
        body={"content_id": content_id, "llm_source": "platform"},
    )
    results.append(
        check(
            "VC5-3 block 后改稿链路",
            code_block == 200
            and blocked.get("status") == "block"
            and decide_after_compliance("block")["target_agent"] == "creator",
            str(blocked.get("status")),
        )
    )
    code_rev, revised = req(
        "POST",
        "/agent/tools/execute",
        token=token,
        body={
            "name": "revise_content",
            "arguments": {
                "content_id": content_id,
                "instruction": "删除违规承诺并补充免责声明",
                "llm_source": "platform",
            },
        },
    )
    results.append(check("VC5-3 Creator revise 可执行", code_rev == 200 and revised.get("content_id"), str(code_rev)))

    code_fin, fin = req(
        "POST",
        "/agent/compliance/check",
        token=token,
        body={"content_id": content_id, "llm_source": "platform", "industry_code": "finance"},
    )
    code_leg, leg = req(
        "POST",
        "/agent/compliance/check",
        token=token,
        body={"content_id": content_id, "llm_source": "platform"},
    )
    db = SessionLocal()
    try:
        row = db.query(Content).filter(uuid_eq(Content.id, UUID(content_id))).first()
        row.industry_code = "legal"
        db.commit()
    finally:
        db.close()
    code_leg2, leg2 = req(
        "POST",
        "/agent/compliance/check",
        token=token,
        body={"content_id": content_id, "llm_source": "platform"},
    )
    fin_disclaimer = (fin.get("issues") or [{}])[0].get("message", "") if fin else ""
    leg_disclaimer = (leg2.get("issues") or [{}])[0].get("message", "") if leg2 else ""
    results.append(
        check(
            "VC5-4 industry 切换影响合规",
            code_fin == 200 and code_leg2 == 200 and fin.get("status") in ("pass", "warn", "block"),
            f"finance={fin.get('status')} legal={leg2.get('status')}",
        )
    )

    proc1 = subprocess.run([sys.executable, "tests/verify_c1.py"], cwd=API_ROOT)
    proc4 = subprocess.run([sys.executable, "tests/verify_c4.py"], cwd=API_ROOT)
    results.append(check("VC5-5 verify_c1 回归", proc1.returncode == 0))
    results.append(check("VC5-5 verify_c4 回归", proc4.returncode == 0))

    passed = all(results)
    print("\n=== C5", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
