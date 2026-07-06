"""B3 验收：revise_content 改稿工具。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

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


def main() -> int:
    results: list[bool] = []

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    user_token = login("13900000099", "test123456")

    code, session = req(
        "POST",
        "/agent/sessions",
        token=user_token,
        body={"industry_code": "finance", "title": "B3改稿"},
    )
    sid = session.get("id")

    code, quota = req("GET", "/settings/llm/quota", token=user_token)
    used_before = quota.get("used_count", 0)

    code, chat = req(
        "POST",
        f"/agent/sessions/{sid}/chat",
        token=user_token,
        body={"message": "生成正文", "selected_proposal_index": 0, "llm_source": "platform"},
    )
    if chat.get("action") != "generate":
        code, chat = req(
            "POST",
            f"/agent/sessions/{sid}/chat",
            token=user_token,
            body={"message": "写一篇公众号报税提醒", "llm_source": "platform"},
        )
        code, chat = req(
            "POST",
            f"/agent/sessions/{sid}/chat",
            token=user_token,
            body={"message": "生成正文", "selected_proposal_index": 0, "llm_source": "platform"},
        )

    content_id = (chat.get("content") or {}).get("id")
    if not content_id:
        print("[FAIL] 无法生成测试正文", chat)
        return 1

    code, detail = req("GET", f"/content/{content_id}", token=user_token)
    body_before = detail.get("body", "")

    code, revised = req(
        "POST",
        "/agent/tools/execute",
        token=user_token,
        body={
            "name": "revise_content",
            "arguments": {"content_id": content_id, "instruction": "缩短20%"},
        },
    )
    code2, detail2 = req("GET", f"/content/{content_id}", token=user_token)
    body_after = detail2.get("body", "")

    results.append(
        check(
            "VB3-1 改稿同 content_id",
            code == 200 and revised.get("content_id") == content_id,
            str(revised)[:80],
        )
    )
    results.append(
        check(
            "VB3-1 正文变化",
            body_before != body_after and "改稿" in body_after,
            body_after[:60],
        )
    )

    code3, quota3 = req("GET", "/settings/llm/quota", token=user_token)
    results.append(
        check(
            "VB3-3 改稿不扣额",
            quota3.get("used_count") == used_before + (1 if chat.get("action") == "generate" else 0),
            f"used {used_before}->{quota3.get('used_count')}",
        )
    )

    code, _ = req(
        "POST",
        "/agent/tools/execute",
        token=user_token,
        body={
            "name": "revise_content",
            "arguments": {"content_id": str(uuid4()), "instruction": "test"},
        },
    )
    results.append(check("VB3-4 不存在 content 404", code == 404, str(code)))

    proc = subprocess.run([sys.executable, "tests/verify_b2.py"], cwd=API_ROOT)
    results.append(check("VB3-5 verify_b2 回归", proc.returncode == 0))

    passed = all(results)
    print("\n=== B3", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
