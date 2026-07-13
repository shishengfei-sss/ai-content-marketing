"""C6 验收：SeoAgent + 会话历史。"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import _get_test_client, check, req, reset_all_tenant_quotas, ensure_fake_platform


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    reset_all_tenant_quotas()
    results: list[bool] = []
    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    token = login("13900000099", "test123456")
    client = _get_test_client()

    marker = f"C6SEO_{uuid4().hex[:8]}"
    code, wf = req(
        "POST",
        "/agent/workflows",
        token=token,
        body={
            "pipeline_code": "content_create",
            "auto_run": True,
            "input": {
                "platform": "wechat",
                "topic": f"SEO测试 {marker}",
                "scene": "brand_intro",
                "content_format": "article",
                "industry_code": "marketing",
                "llm_source": "platform",
                "search_query": "报税",
            },
        },
    )
    import json

    output = json.loads(wf.get("output_json") or "{}") if wf.get("output_json") else {}
    content_id = output.get("content_id")
    results.append(check("VC6-0 工作流产出 content", code == 200 and content_id, str(content_id)))

    code, quota_before = req("GET", "/settings/llm/quota", token=token)
    used_before = quota_before.get("used_count", 0)

    code, seo = req(
        "POST",
        "/agent/seo/optimize",
        token=token,
        body={"content_id": content_id, "llm_source": "platform"},
    )
    titles = seo.get("title_candidates") or [] if isinstance(seo, dict) else []
    tags = seo.get("tags") or [] if isinstance(seo, dict) else []
    results.append(
        check(
            "VC6-1 SEO ≥3 标题 + tags",
            code == 200 and len(titles) >= 3 and len(tags) >= 1,
            f"titles={len(titles)} tags={len(tags)}",
        )
    )

    code, quota_after = req("GET", "/settings/llm/quota", token=token)
    used_after = quota_after.get("used_count", 0)
    results.append(
        check(
            "VC6-2 optimize 不扣额度",
            code == 200 and used_after == used_before,
            f"{used_before}->{used_after}",
        )
    )

    code, tool_seo = req(
        "POST",
        "/agent/tools/execute",
        token=token,
        body={"name": "optimize_metadata", "arguments": {"content_id": content_id}},
    )
    results.append(
        check(
            "VC6-1 工具 optimize_metadata",
            code == 200 and len((tool_seo or {}).get("title_candidates") or []) >= 3,
            str(code),
        )
    )

    r_agents = client.get("/api/v1/agent/supervisor/agents", headers={"Authorization": f"Bearer {token}"})
    agent_codes = {a["code"] for a in (r_agents.json().get("agents") or [])}
    results.append(check("VC6-1 注册 seo agent", "seo" in agent_codes, str(sorted(agent_codes))))

    code, s1 = req("POST", "/agent/sessions", token=token, body={"title": f"C6旧会话 {marker}"})
    time.sleep(0.05)
    code, s2 = req("POST", "/agent/sessions", token=token, body={"title": f"C6新会话 {marker}"})
    sid_old, sid_new = s1.get("id"), s2.get("id")
    req(
        "POST",
        f"/agent/sessions/{sid_old}/messages",
        token=token,
        body={"role": "user", "content": "刷新 updated_at"},
    )

    r_list = client.get(
        "/api/v1/agent/sessions",
        params={"limit": 20},
        headers={"Authorization": f"Bearer {token}"},
    )
    sessions = r_list.json() if r_list.status_code == 200 else []
    ids = [s.get("id") for s in sessions]
    idx_old = ids.index(sid_old) if sid_old in ids else 999
    idx_new = ids.index(sid_new) if sid_new in ids else 999
    results.append(
        check(
            "VC6-3 会话列表 updated_at 排序",
            r_list.status_code == 200 and len(sessions) <= 20 and idx_old < idx_new,
            f"old={idx_old} new={idx_new}",
        )
    )

    r_one = client.get(
        f"/api/v1/agent/sessions/{sid_new}",
        headers={"Authorization": f"Bearer {token}"},
    )
    results.append(
        check(
            "VC6-3 单条会话可查",
            r_one.status_code == 200 and r_one.json().get("id") == sid_new,
            str(r_one.status_code),
        )
    )

    web_create = API_ROOT.parent / "web" / "src" / "views" / "Create.vue"
    mp_create = API_ROOT.parent / "mp" / "src" / "pages" / "create" / "create.vue"
    web_text = web_create.read_text(encoding="utf-8") if web_create.is_file() else ""
    mp_text = mp_create.read_text(encoding="utf-8") if mp_create.is_file() else ""
    results.append(
        check(
            "VC6-3 Web 历史会话 UI",
            "listSessions" in web_text and "openSessionHistory" in web_text,
            "Create.vue",
        )
    )
    results.append(
        check(
            "VC6-3 H5 历史会话 UI",
            "listSessions" in mp_text and "openSessionHistory" in mp_text,
            "create.vue",
        )
    )

    proc = subprocess.run([sys.executable, "-B", "tests/verify_c5.py"], cwd=API_ROOT)
    results.append(check("VC6-4 verify_c5 回归", proc.returncode == 0))

    passed = all(results)
    print("\n=== C6", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
