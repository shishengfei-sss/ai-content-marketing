"""A2 验收：Agent 意图 Chat。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, ensure_fake_platform, req


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def chat(token: str, sid: str, message: str, **extra):
    body = {"message": message, "llm_source": "platform", **extra}
    return req("POST", f"/agent/sessions/{sid}/chat", token=token, body=body)


def main() -> int:
    results: list[bool] = []

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)

    user_token = login("13900000099", "test123456")

    code, session = req(
        "POST",
        "/agent/sessions",
        token=user_token,
        body={"industry_code": "finance", "title": "A2测试"},
    )
    if code != 200:
        print("[FAIL] 创建会话", code, session)
        return 1
    sid = session["id"]

    code, quota = req("GET", "/settings/llm/quota", token=user_token)
    used_before = quota.get("used_count", 0) if code == 200 else 0

    code, resp = chat(user_token, sid, "写一篇公众号报税提醒")
    code2, quota2 = req("GET", "/settings/llm/quota", token=user_token)
    results.append(
        check(
            "VA2-1 proposals不扣额度",
            code == 200
            and resp.get("action") == "proposals"
            and len(resp.get("proposals") or []) >= 1
            and quota2.get("used_count") == used_before,
            f"action={resp.get('action')} used={used_before}->{quota2.get('used_count')}",
        )
    )

    code, resp = chat(user_token, sid, "帮我写点东西")
    results.append(
        check(
            "VA2-3 缺参clarify",
            code == 200 and resp.get("action") == "clarify" and bool(resp.get("clarify_question")),
            str(resp.get("action")),
        )
    )

    code, resp = chat(user_token, sid, "生成正文", selected_proposal_index=0)
    code3, quota3 = req("GET", "/settings/llm/quota", token=user_token)
    body_text = (resp.get("content") or {}).get("body", "")
    results.append(
        check(
            "VA2-2 generate扣1次额度",
            code == 200
            and resp.get("action") == "generate"
            and resp.get("content", {}).get("id")
            and quota3.get("used_count") == used_before + 1,
            f"generate={code} used->{quota3.get('used_count')}",
        )
    )
    results.append(
        check(
            "VA2-4 正文含免责声明",
            "仅供参考" in body_text or "税务机关" in body_text,
            body_text[:80],
        )
    )

    code, err = chat(user_token, sid, "我要发抖音文章")
    detail = err.get("detail") if isinstance(err, dict) else str(err)
    results.append(
        check(
            "VA2-5 douyin+article 400",
            code == 400 and "内容形态" in str(detail),
            str(code) + " " + str(detail)[:60],
        )
    )

    proc = subprocess.run([sys.executable, "tests/run_m0_m8.py"], cwd=API_ROOT)
    results.append(check("VA2-7 run_m0_m8", proc.returncode == 0))

    passed = all(results)
    print("\n=== A2", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
