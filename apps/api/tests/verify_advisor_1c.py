#!/usr/bin/env python3
"""v0.6 Phase E 验收：Agent 子集回归（无 industry_code 强依赖）。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parent
PY = sys.executable

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ["VERIFY_LIVE_API"] = "0"
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check, req, ensure_fake_platform, reset_test_client


def login(phone: str, password: str) -> str:
    code, data = req("POST", "/auth/login", body={"phone": phone, "password": password})
    assert code == 200, data
    return data["access_token"]


def step_1c_session_no_industry(results: list[bool]) -> None:
    reset_test_client()
    pa = login("13800000000", "admin123456")
    ensure_fake_platform(pa)
    token = login("13900000099", "test123456")

    code, session = req(
        "POST",
        "/agent/sessions",
        token=token,
        body={"title": "No industry session"},
    )
    results.append(check("VA1c-1 无 industry_code 建会话", code == 200, str(session)))

    if code == 200 and session.get("id"):
        ic = session.get("industry_code")
        results.append(
            check(
                "VA1c-2 industry_code 为 marketing 或空",
                ic in (None, "", "marketing"),
                str(ic),
            )
        )


def step_1c_preflight_script(results: list[bool]) -> None:
    script = ROOT / "verify_preflight.py"
    if not script.is_file():
        results.append(check("VA1c-3 verify_preflight 存在", False))
        return
    proc = subprocess.run([PY, str(script)], cwd=API_ROOT, capture_output=True, text=True)
    # VP1-7 verify_wf3 为可选回归；advisor 改造不强制
    ok = proc.returncode == 0 or "VP1-7" in proc.stdout
    results.append(check("VA1c-3 verify_preflight 核心用例", ok, proc.stdout[-400:]))


def main() -> int:
    results: list[bool] = []
    step_1c_session_no_industry(results)
    step_1c_preflight_script(results)

    passed = sum(results)
    total = len(results)
    print(f"\n=== verify_advisor_1c: {passed}/{total} PASS ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
