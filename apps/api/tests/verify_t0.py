"""T0 验收：FakeLLM 与 unit 测试。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.http_client import check


def main() -> int:
    results: list[bool] = []

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit/test_fake_llm.py", "-q"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    results.append(check("VT0-1 pytest fake_llm", proc.returncode == 0, out.strip()[:200]))

    from app.services.llm.factory import get_provider

    p = get_provider("fake")
    results.append(check("VT0-2 factory fake provider", p.provider_name == "fake"))

    passed = all(results)
    print("\n=== T0", "全部通过" if passed else "存在失败", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
