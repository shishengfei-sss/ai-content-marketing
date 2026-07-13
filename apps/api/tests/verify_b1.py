"""B1 验收：Agent Tool Registry。"""
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


def main() -> int:
    results: list[bool] = []

    admin_token = login("13900000099", "test123456")

    code, tools = req("GET", "/agent/tools", token=admin_token)
    names = {t["name"] for t in tools} if isinstance(tools, list) else set()
    results.append(
        check(
            "VB1-1 注册表≥8工具",
            code == 200 and len(names) >= 8,
            str(sorted(names))[:120],
        )
    )
    for required in (
        "list_scenes",
        "search_knowledge",
        "generate_proposals",
        "generate_content",
        "get_quota",
    ):
        results.append(check(f"VB1-1 含 {required}", required in names))

    editor_token = login("13900008888", "Test123456")
    code, me = req("GET", "/auth/me", token=editor_token)
    if me.get("need_select_tenant") and me.get("tenants"):
        code, sel = req(
            "POST",
            "/auth/select-tenant",
            token=editor_token,
            body={"tenant_id": me["tenants"][1]["id"]},
        )
        editor_token = sel["access_token"]

    code, editor_tools = req("GET", "/agent/tools", token=editor_token)
    editor_names = {t["name"] for t in editor_tools} if isinstance(editor_tools, list) else set()
    results.append(
        check(
            "VB1-2 无 publish 权限则不可见 publish_content",
            "publish_content" not in editor_names,
            str("publish_content" in editor_names),
        )
    )

    marker = f"B1MARKER_{uuid4().hex[:8]}"
    req(
        "POST",
        "/knowledge/documents/text",
        token=admin_token,
        body={
            "title": "B1隔离测试",
            "text": f"租户私有知识 {marker} 内容片段用于检索验证",
            "industry_code": "marketing",
        },
    )
    code, search = req(
        "POST",
        "/agent/tools/execute",
        token=admin_token,
        body={"name": "search_knowledge", "arguments": {"query": marker}},
    )
    scopes = [r.get("scope") for r in (search.get("results") or [])] if isinstance(search, dict) else []
    results.append(
        check(
            "VB1-3 search_knowledge 租户命中",
            code == 200 and "tenant" in scopes,
            str(scopes),
        )
    )

    code, quota = req(
        "POST",
        "/agent/tools/execute",
        token=admin_token,
        body={"name": "get_quota", "arguments": {}},
    )
    results.append(
        check(
            "VB1-4 execute get_quota",
            code == 200 and "remaining" in (quota or {}),
            str(code),
        )
    )

    proc = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/test_agent_tools.py", "-q"], cwd=API_ROOT)
    results.append(check("VB1-4 unit test_agent_tools", proc.returncode == 0))

    proc2 = subprocess.run([sys.executable, "-B", "tests/run_m0_m8.py"], cwd=API_ROOT)
    results.append(check("VB1-5 run_m0_m8", proc2.returncode == 0))

    passed = all(results)
    print("\n=== B1", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
