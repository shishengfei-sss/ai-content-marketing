"""CRM 每步回归：v0.3.3 必跑；v0.4 Agent 可选（VERIFY_SKIP_AGENT=1 跳过）。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API_ROOT = ROOT.parent
PY = sys.executable

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")


def _run(script: str) -> int:
    print(f"\n>>> regression: {script}")
    r = subprocess.run([PY, str(ROOT / script)], cwd=API_ROOT)
    return r.returncode


def main() -> int:
    failed = []
    scripts = ["run_m0_m8.py"]
    if os.environ.get("VERIFY_SKIP_AGENT") != "1":
        scripts.append("run_agent_a_c.py")
    for script in scripts:
        if _run(script) != 0:
            failed.append(script)
    if failed:
        print("\n=== CRM 回归失败 ===", ", ".join(failed))
        return 1
    print("\n=== CRM 回归通过 ===", ", ".join(scripts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())