"""A1 验收：Agent 会话持久化。"""
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


def main() -> int:
    results: list[bool] = []

    admin_token = login("13900000099", "test123456")
    pa_token = login("13800000000", "admin123456")

    code, session = req(
        "POST",
        "/agent/sessions",
        token=admin_token,
        body={"industry_code": "marketing", "title": "A1测试会话"},
    )
    results.append(check("VA1-1 创建会话", code == 200 and session.get("id"), str(session)[:80]))
    sid = session.get("id")

    code, _ = req("POST", "/agent/sessions", token=pa_token, body={"title": "x"})
    results.append(check("VA1-4 平台管理员403", code == 403, str(code)))

    if sid:
        for i, (role, content) in enumerate(
            [
                ("user", "第一条"),
                ("assistant", "第二条"),
                ("user", "第三条"),
            ]
        ):
            code, _ = req(
                "POST",
                f"/agent/sessions/{sid}/messages",
                token=admin_token,
                body={"role": role, "content": content},
            )
            if code != 200:
                results.append(check(f"VA1-3 追加消息{i+1}", False, str(code)))
                break
        else:
            code, messages = req("GET", f"/agent/sessions/{sid}/messages", token=admin_token)
            ok = (
                code == 200
                and len(messages) == 3
                and messages[0]["content"] == "第一条"
                and messages[2]["content"] == "第三条"
            )
            results.append(check("VA1-3 消息顺序", ok, str(len(messages) if isinstance(messages, list) else messages)))

    code, sessions = req("GET", "/agent/sessions", token=admin_token)
    results.append(
        check(
            "VA1-1 列表会话",
            code == 200 and isinstance(sessions, list) and len(sessions) >= 1,
            str(len(sessions) if isinstance(sessions, list) else code),
        )
    )

    proc = subprocess.run([sys.executable, "-B", "tests/run_m0_m8.py"], cwd=API_ROOT)
    results.append(check("VA1-5 run_m0_m8", proc.returncode == 0))

    passed = all(results)
    print("\n=== A1", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
