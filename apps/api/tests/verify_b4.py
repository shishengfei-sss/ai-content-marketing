"""B4 验收：Agent Chat SSE 流式。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

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


def parse_sse_response(response) -> tuple[str, list[tuple[str, dict]]]:
    content_type = response.headers.get("content-type", "")
    events: list[tuple[str, dict]] = []
    current_event = ""
    for line in response.iter_lines():
        if not line:
            continue
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            payload = line[6:]
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = {"raw": payload}
            events.append((current_event, data))
    return content_type, events


def stream_chat(token: str, sid: str, message: str, **extra):
    client = _get_test_client()
    headers = {"Authorization": f"Bearer {token}"}
    body = {"message": message, "llm_source": "platform", **extra}
    with client.stream(
        "POST",
        f"/api/v1/agent/sessions/{sid}/chat/stream",
        json=body,
        headers=headers,
    ) as response:
        content_type, events = parse_sse_response(response)
        return response.status_code, content_type, events


def main() -> int:
    results: list[bool] = []

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    user_token = login("13900000099", "test123456")

    code, session = req(
        "POST",
        "/agent/sessions",
        token=user_token,
        body={"industry_code": "finance", "title": "B4 SSE"},
    )
    sid = session.get("id")
    if not sid:
        print("[FAIL] 创建会话失败")
        return 1

    code, ctype, events = stream_chat(user_token, sid, "写一篇公众号报税提醒")
    deltas = [e for e in events if e[0] == "delta"]
    done = next((e[1] for e in events if e[0] == "done"), None)

    results.append(check("VB4-1 SSE Content-Type", "text/event-stream" in ctype, ctype))
    results.append(check("VB4-2 delta 事件≥2", len(deltas) >= 2, str(len(deltas))))
    results.append(
        check(
            "VB4-3 done 含 action=proposals",
            code == 200 and done and done.get("action") == "proposals" and done.get("proposals"),
            str(done.get("action") if done else None),
        )
    )

    code2, _, events2 = stream_chat(
        user_token,
        sid,
        "生成正文",
        selected_proposal_index=0,
    )
    deltas2 = [e for e in events2 if e[0] == "delta"]
    done2 = next((e[1] for e in events2 if e[0] == "done"), None)
    results.append(
        check(
            "VB4-4 generate 流式正文",
            code2 == 200 and len(deltas2) >= 2 and done2 and done2.get("action") == "generate",
            f"deltas={len(deltas2)} action={done2.get('action') if done2 else None}",
        )
    )

    code3, data = req(
        "POST",
        f"/agent/sessions/{sid}/chat",
        token=user_token,
        body={"message": "帮我写点东西", "llm_source": "platform", "mode": "legacy"},
    )
    results.append(check("VB4-5 非流式 chat 仍可用", code3 == 200 and data.get("action") == "clarify", str(data.get("action"))))

    proc = subprocess.run([sys.executable, "tests/verify_b3.py"], cwd=API_ROOT)
    results.append(check("VB4-6 verify_b3 回归", proc.returncode == 0))

    passed = all(results)
    print("\n=== B4", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
