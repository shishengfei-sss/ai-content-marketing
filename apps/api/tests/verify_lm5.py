"""LM5 验收：hybrid recall（关键词 + 词元重叠，C4 前奏）。"""
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
        body={"scope": "user", "fact_text": "擅长小红书种草笔记写法", "category": "style"},
    )
    req(
        "POST",
        "/agent/memories",
        token=token,
        body={"scope": "user", "fact_text": "公众号深度长文偏严肃风格", "category": "style"},
    )

    r = client.get(
        "/api/v1/agent/recall",
        params={"q": "小红书种草", "mode": "hybrid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    data = r.json()
    facts = data.get("memory_facts") or []
    top = facts[0].get("fact_text", "") if facts else ""
    results.append(
        check(
            "VLM5-1 hybrid 命中小红书",
            r.status_code == 200 and data.get("mode") == "hybrid" and "小红书" in top,
            top[:50],
        )
    )

    r2 = client.get(
        "/api/v1/agent/recall",
        params={"q": "小红书", "mode": "hybrid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    facts2 = r2.json().get("memory_facts") or []
    results.append(
        check(
            "VLM5-2 排序优于无关记忆",
            facts2 and "小红书" in facts2[0].get("fact_text", ""),
            (facts2[0].get("fact_text", "") if facts2 else "")[:40],
        )
    )

    proc = subprocess.run([sys.executable, "-B", "tests/verify_lm4.py"], cwd=API_ROOT)
    results.append(check("VLM5-3 verify_lm4 回归", proc.returncode == 0))

    passed = all(results)
    print("\n=== LM5", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
