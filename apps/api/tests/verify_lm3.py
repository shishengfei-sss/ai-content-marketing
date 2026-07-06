"""LM3 验收：记忆注入 + token 预算。"""
from __future__ import annotations

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


def main() -> int:
    results: list[bool] = []
    token = login("13900000099", "test123456")
    client = _get_test_client()

    req(
        "POST",
        "/agent/memories",
        token=token,
        body={"scope": "tenant", "fact_text": "公司主打代理记账服务", "category": "brand"},
    )

    r = client.get(
        "/api/v1/agent/memory-context",
        params={"q": "代理记账"},
        headers={"Authorization": f"Bearer {token}"},
    )
    ctx = r.json()
    results.append(
        check(
            "VLM3-1 记忆注入含企业事实",
            r.status_code == 200 and "代理记账" in ctx.get("context", ""),
            ctx.get("context", "")[:80],
        )
    )

    for i in range(8):
        req(
            "POST",
            "/agent/memories",
            token=token,
            body={
                "scope": "user",
                "fact_text": f"测试偏好条目{i}：" + "很长" * 80,
                "category": "preference",
            },
        )
    r2 = client.get(
        "/api/v1/agent/memory-context",
        params={"max_chars": 120},
        headers={"Authorization": f"Bearer {token}"},
    )
    ctx2 = r2.json()
    results.append(
        check(
            "VLM3-2 token 预算截断",
            r2.status_code == 200 and ctx2.get("char_count", 999) <= 120,
            f"chars={ctx2.get('char_count')}",
        )
    )

    code, session = req(
        "POST",
        "/agent/sessions",
        token=token,
        body={"industry_code": "finance", "title": "LM3注入"},
    )
    sid = session.get("id")
    code, chat = req(
        "POST",
        f"/agent/sessions/{sid}/chat",
        token=token,
        body={"message": "帮我写公众号报税提醒", "llm_source": "platform"},
    )
    results.append(check("VLM3-3 chat 仍可用", code == 200 and chat.get("action") == "proposals", chat.get("action")))

    proc = subprocess.run([sys.executable, "tests/verify_lm2.py"], cwd=API_ROOT)
    results.append(check("VLM3-4 verify_lm2 回归", proc.returncode == 0))

    passed = all(results)
    print("\n=== LM3", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
