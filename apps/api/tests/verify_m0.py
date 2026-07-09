"""M0 基线验收：迁移、平台额度、回归（TestClient）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from tests.http_client import _get_test_client, check, req


def main() -> int:
    results: list[bool] = []

    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    results.append(check(f"V0-1 alembic={EXPECTED_HEAD}(head)", is_at_expected_head(out), out.strip()))

    health_resp = _get_test_client().get("/health")
    results.append(check("V0-5 API /health", health_resp.status_code == 200))

    code, admin = req("POST", "/auth/login", body={"phone": "13800000000", "password": "admin123456"})
    results.append(check("V0-4 admin login", code == 200, str(code)))
    if code != 200:
        return 1
    admin_token = admin["access_token"]

    code, platform = req("GET", "/admin/platform-llm", token=admin_token)
    results.append(check("V0-4 platform-llm GET", code == 200, str(platform.get("default_free_quota"))))

    code, user = req("POST", "/auth/login", body={"phone": "13900000099", "password": "test123456"})
    if code != 200:
        req(
            "POST",
            "/auth/register",
            body={
                "phone": "13900000099",
                "password": "test123456",
                "tenant_name": "M0测试公司",
                "industry_code": "finance",
                "display_name": "M0测试",
            },
        )
        code, user = req("POST", "/auth/login", body={"phone": "13900000099", "password": "test123456"})
    results.append(check("V0-5 test user login", code == 200))
    if code != 200:
        return 1
    user_token = user["access_token"]

    code, quota = req("GET", "/settings/llm/quota", token=user_token)
    results.append(
        check(
            "V0-2 quota API",
            code == 200 and "used_count" in quota and "remaining" in quota,
            str(quota),
        )
    )

    used_before = quota.get("used_count", 0)
    code, proposals = req(
        "POST",
        "/content/proposals",
        token=user_token,
        body={
            "industry_code": "finance",
            "platform": "wechat",
            "scene": "bookkeeping_intro",
            "topic": "M0验收测试主题",
            "content_format": "article",
            "llm_source": "platform",
        },
    )
    code2, quota2 = req("GET", "/settings/llm/quota", token=user_token)
    results.append(
        check(
            "V0-3 proposals不扣次",
            code == 200 and quota2.get("used_count") == used_before,
            f"proposals={code} used {used_before}->{quota2.get('used_count')}",
        )
    )

    if code == 200 and proposals.get("proposals"):
        sel = proposals["proposals"][0]
        code, _ = req(
            "POST",
            "/content/generate",
            token=user_token,
            body={
                "industry_code": "finance",
                "platform": "wechat",
                "scene": "bookkeeping_intro",
                "topic": "M0验收测试主题",
                "content_format": "article",
                "llm_source": "platform",
                "selected_proposal": sel,
            },
        )
        code3, quota3 = req("GET", "/settings/llm/quota", token=user_token)
        results.append(
            check(
                "V0-3 generate扣1次",
                code == 200 and quota3.get("used_count") == used_before + 1,
                f"generate={code} used->{quota3.get('used_count')}",
            )
        )

    passed = all(results)
    print("\n=== M0", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
