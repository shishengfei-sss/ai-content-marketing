"""A0 验收：Agent 迁移与健康检查。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import is_at_expected_head
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
    results.append(check("VA0-1 alembic=022(head)", is_at_expected_head(out), out.strip()))

    r = _get_test_client().get("/api/v1/agent/health")
    results.append(check("VA0-2 agent health", r.status_code == 200 and r.json().get("status") == "ok"))

    proc2 = subprocess.run([sys.executable, "tests/run_m0_m8.py"], cwd=API_ROOT)
    results.append(check("VA0-3 run_m0_m8", proc2.returncode == 0))

    openapi = _get_test_client().get("/openapi.json").json()
    paths = openapi.get("paths", {})
    results.append(check("VA0-4 openapi agent/health", "/api/v1/agent/health" in paths))

    passed = all(results)
    print("\n=== A0", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
