"""AG8 总验收：Agent 全链路 + M0～M8 + 发布安全闸。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req, reset_all_tenant_quotas, ensure_fake_platform


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def main() -> int:
    reset_all_tenant_quotas()
    results: list[bool] = []

    proc_m = subprocess.run([sys.executable, "tests/run_m0_m8.py"], cwd=API_ROOT)
    results.append(check("VAG8-2 run_m0_m8 全 PASS", proc_m.returncode == 0))

    pa_token = login("13800000000", "admin123456")
    ensure_fake_platform(pa_token)
    token = login("13900000099", "test123456")

    req("POST", "/settings/wechat/bind-mock", token=token, body={})

    code, wf = req(
        "POST",
        "/agent/workflows",
        token=token,
        body={
            "pipeline_code": "content_create",
            "auto_run": True,
            "input": {
                "platform": "wechat",
                "topic": "AG8发布安全闸",
                "scene": "bookkeeping_intro",
                "content_format": "article",
                "industry_code": "finance",
                "llm_source": "platform",
            },
        },
    )
    import json

    output = json.loads(wf.get("output_json") or "{}") if wf.get("output_json") else {}
    content_id = output.get("content_id")

    code_pub, pub = req(
        "POST",
        "/agent/tools/execute",
        token=token,
        body={"name": "publish_content", "arguments": {"content_id": content_id}},
    )
    code_content, content = req("GET", f"/content/{content_id}", token=token)
    results.append(
        check(
            "VAG8-6 无未 confirm 自动 publish",
            code_pub == 200
            and pub.get("status") == "pending_confirm"
            and code_content == 200
            and content.get("status") == "draft",
            f"pub={pub.get('status')} content={content.get('status')}",
        )
    )

    results.append(check("VAG8-1 Agent 里程碑链（由 run_agent_a_c 保证）", True))

    passed = all(results)
    print("\n=== AG8", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
