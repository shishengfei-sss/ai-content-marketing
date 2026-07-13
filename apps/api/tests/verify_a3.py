"""A3 验收：Web/H5 创作页接入 Agent API。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
WEB_CREATE = API_ROOT.parent / "web" / "src" / "views" / "Create.vue"
MP_CREATE = API_ROOT.parent / "mp" / "src" / "pages" / "create" / "create.vue"
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req, ensure_fake_platform


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]



def main() -> int:
    results: list[bool] = []

    web_text = WEB_CREATE.read_text(encoding="utf-8") if WEB_CREATE.is_file() else ""
    mp_text = MP_CREATE.read_text(encoding="utf-8") if MP_CREATE.is_file() else ""
    results.append(
        check(
            "VA3-1 Web Create.vue 接 agentApi",
            "agentApi" in web_text and "agentApi.chat" in web_text,
            "agentApi.chat" if "agentApi" in web_text else "missing",
        )
    )
    results.append(
        check(
            "VA3-2 H5 create.vue 接 agentApi",
            "agentApi" in mp_text and "agentApi.chat" in mp_text,
            "agentApi.chat" if "agentApi" in mp_text else "missing",
        )
    )

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    user_token = login("13900000099", "test123456")

    code, session = req(
        "POST",
        "/agent/sessions",
        token=user_token,
        body={"industry_code": "marketing", "title": "A3 E2E"},
    )
    sid = session.get("id") if code == 200 else None
    results.append(check("VA3-3 创建 Agent 会话", code == 200 and bool(sid), str(code)))

    if sid:
        code, quota = req("GET", "/settings/llm/quota", token=user_token)
        used_before = quota.get("used_count", 0) if code == 200 else 0

        code, resp = req(
            "POST",
            f"/agent/sessions/{sid}/chat",
            token=user_token,
            body={"message": "写一篇公众号报税提醒", "llm_source": "platform"},
        )
        results.append(
            check(
                "VA3-3 chat 出方案",
                code == 200 and resp.get("action") == "proposals" and len(resp.get("proposals") or []) >= 1,
                resp.get("action") if isinstance(resp, dict) else str(code),
            )
        )

        code, resp = req(
            "POST",
            f"/agent/sessions/{sid}/chat",
            token=user_token,
            body={
                "message": "生成正文",
                "llm_source": "platform",
                "selected_proposal_index": 0,
            },
        )
        content_id = (resp.get("content") or {}).get("id") if isinstance(resp, dict) else None
        code2, quota2 = req("GET", "/settings/llm/quota", token=user_token)
        results.append(
            check(
                "VA3-3 chat 出正文",
                code == 200 and resp.get("action") == "generate" and bool(content_id),
                str(resp.get("action") if isinstance(resp, dict) else code),
            )
        )
        results.append(
            check(
                "VA3-5 正文后额度-1",
                quota2.get("used_count") == used_before + 1,
                f"{used_before}->{quota2.get('used_count')}",
            )
        )

        if content_id:
            code, listed = req("GET", "/content", token=user_token, body=None)
            items = listed.get("items") if isinstance(listed, dict) else listed
            found = any(str(item.get("id")) == str(content_id) for item in (items or []))
            results.append(check("VA3-3 内容库可见", code == 200 and found, str(content_id)[:8]))

    proc = subprocess.run([sys.executable, "-B", "tests/run_m0_m8.py"], cwd=API_ROOT)
    results.append(check("VA3-6 run_m0_m8", proc.returncode == 0))

    passed = all(results)
    print("\n=== A3", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
