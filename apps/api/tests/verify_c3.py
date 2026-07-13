"""C3 验收：Confirm 闸 + OpsAgent。"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
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


def table_exists(table: str) -> bool:
    from sqlalchemy import inspect

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        return table in inspect(db.bind).get_table_names()
    finally:
        db.close()


def create_content(token: str) -> str:
    code, wf = req(
        "POST",
        "/agent/workflows",
        token=token,
        body={
            "pipeline_code": "content_create",
            "auto_run": True,
            "input": {
                "platform": "wechat",
                "topic": "C3发布测试",
                "scene": "brand_intro",
                "content_format": "article",
                "industry_code": "marketing",
                "llm_source": "platform",
            },
        },
    )
    assert code == 200 and wf.get("status") == "completed", wf
    output = json.loads(wf.get("output_json") or "{}")
    return output["content_id"]


def main() -> int:
    results: list[bool] = []

    out = alembic_head()
    results.append(check("VC3-1 alembic=022(head)", is_at_expected_head(out), out.strip()))
    results.append(check("VC3-1 表 agent_pending_actions", table_exists("agent_pending_actions")))

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    token = login("13900000099", "test123456")

    req(
        "POST",
        "/settings/wechat/bind-mock",
        token=token,
        body={"account_name": "C3测试号", "account_type": "service"},
    )

    content_id = create_content(token)

    code, pending_pub = req(
        "POST",
        "/agent/tools/execute",
        token=token,
        body={"name": "publish_content", "arguments": {"content_id": content_id}},
    )
    action_id = pending_pub.get("action_id")
    results.append(
        check(
            "VC3-2 publish 创建待确认",
            code == 200 and pending_pub.get("status") == "pending_confirm" and action_id,
            str(pending_pub.get("status")),
        )
    )

    code2, content = req("GET", f"/content/{content_id}", token=token)
    results.append(check("VC3-3 未 confirm 不发布", code2 == 200 and content.get("status") == "draft", content.get("status")))

    code3, confirmed = req("POST", f"/agent/ops/actions/{action_id}/confirm", token=token)
    results.append(
        check(
            "VC3-4 confirm 后发布",
            code3 == 200 and confirmed.get("status") == "confirmed",
            str(confirmed),
        )
    )
    code4, content2 = req("GET", f"/content/{content_id}", token=token)
    results.append(check("VC3-4 内容已发布", code4 == 200 and content2.get("status") == "published", content2.get("status")))

    content_id2 = create_content(token)
    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0).isoformat()
    code5, pending_sched = req(
        "POST",
        "/agent/tools/execute",
        token=token,
        body={
            "name": "schedule_content",
            "arguments": {"content_id": content_id2, "scheduled_at": scheduled_at},
        },
    )
    sched_action_id = pending_sched.get("action_id")
    results.append(
        check(
            "VC3-5 schedule 待确认",
            code5 == 200 and pending_sched.get("status") == "pending_confirm",
            str(pending_sched.get("status")),
        )
    )

    code6, cancelled = req("POST", f"/agent/ops/actions/{sched_action_id}/cancel", token=token)
    results.append(
        check(
            "VC3-6 可取消待确认",
            code6 == 200 and cancelled.get("status") == "cancelled",
            str(cancelled.get("status")),
        )
    )

    code7, pending_list = req("GET", "/agent/ops/pending", token=token)
    results.append(check("VC3-7 pending 列表", code7 == 200 and isinstance(pending_list, list), str(len(pending_list))))

    proc = subprocess.run([sys.executable, "-B", "tests/verify_c2.py"], cwd=API_ROOT)
    results.append(check("VC3-8 verify_c2 回归", proc.returncode == 0))

    passed = all(results)
    print("\n=== C3", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
