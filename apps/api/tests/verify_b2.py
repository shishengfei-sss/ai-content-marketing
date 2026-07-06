"""B2 验收：ReAct 多步 Tool 循环。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

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


def react_chat(token: str, sid: str, message: str):
    return req(
        "POST",
        f"/agent/sessions/{sid}/chat",
        token=token,
        body={"message": message, "llm_source": "platform", "mode": "react"},
    )


def main() -> int:
    results: list[bool] = []

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    user_token = login("13900000099", "test123456")

    code, session = req(
        "POST",
        "/agent/sessions",
        token=user_token,
        body={"industry_code": "finance", "title": "B2 ReAct"},
    )
    sid = session.get("id") if code == 200 else None
    if not sid:
        print("[FAIL] 创建会话失败")
        return 1

    code, quota = req("GET", "/settings/llm/quota", token=user_token)
    used_before = quota.get("used_count", 0) if code == 200 else 0

    code, resp = react_chat(user_token, sid, "先查知识库再写小红书种草")
    code, messages = req("GET", f"/agent/sessions/{sid}/messages", token=user_token)
    tool_calls = [
        m for m in (messages if isinstance(messages, list) else []) if m.get("message_type") == "tool_call"
    ]
    tool_results = [
        m for m in (messages if isinstance(messages, list) else []) if m.get("message_type") == "tool_result"
    ]
    results.append(
        check(
            "VB2-1 多步 tool_call≥2",
            code == 200 and len(tool_calls) >= 2,
            f"calls={len(tool_calls)}",
        )
    )
    results.append(
        check(
            "VB2-2 messages 含 tool 名与结果",
            len(tool_calls) >= 2
            and len(tool_results) >= 2
            and all(m.get("metadata_json") for m in tool_calls + tool_results),
            str(len(tool_results)),
        )
    )

    code2, quota2 = req("GET", "/settings/llm/quota", token=user_token)
    results.append(
        check(
            "VB2-4 ReAct 检索+方案不扣额",
            quota2.get("used_count") == used_before,
            f"{used_before}->{quota2.get('used_count')}",
        )
    )

    code, session2 = req(
        "POST",
        "/agent/sessions",
        token=user_token,
        body={"industry_code": "finance", "title": "B2 循环测试"},
    )
    sid2 = session2.get("id")
    code, resp_fail = react_chat(user_token, sid2, "INFINITE_LOOP_TEST")
    code, session_detail = req("GET", f"/agent/sessions/{sid2}", token=user_token)
    status = session_detail.get("status") if isinstance(session_detail, dict) else None
    results.append(
        check(
            "VB2-3 超步数终止 failed",
            code == 200 and resp_fail.get("action") == "failed" and status == "failed",
            f"action={resp_fail.get('action')} status={status}",
        )
    )

    proc = subprocess.run([sys.executable, "tests/verify_a2.py"], cwd=API_ROOT)
    results.append(check("VB2-5 verify_a2 回归", proc.returncode == 0))
    proc2 = subprocess.run([sys.executable, "tests/run_m0_m8.py"], cwd=API_ROOT)
    results.append(check("VB2-5 run_m0_m8", proc2.returncode == 0))

    passed = all(results)
    print("\n=== B2", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
