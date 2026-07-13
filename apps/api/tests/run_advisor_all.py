#!/usr/bin/env python3
"""串联 v0.6 通用顾问验收脚本（见 docs/v0.6-advisor执行计划.md）。"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parent
PY = sys.executable

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ["VERIFY_LIVE_API"] = "0"

STEPS: list[tuple[str, str]] = [
    ("0a", "verify_advisor_0a.py"),
    ("1a", "verify_advisor_1a.py"),
    ("1b", "verify_advisor_1b.py"),
    ("1c", "verify_advisor_1c.py"),
    ("1d", "verify_advisor_1d.py"),
    ("bd", "verify_advisor_bd.py"),
    ("ue", "verify_advisor_ue.py"),
    ("pl", "verify_advisor_persona.py"),
    ("comp", "verify_advisor_compliance.py"),
]

THROUGH_ORDER = [name for name, _ in STEPS]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run advisor verify scripts in order")
    parser.add_argument(
        "--through",
        choices=THROUGH_ORDER,
        help="Run scripts up to and including this phase (e.g. 0a, 1a)",
    )
    args = parser.parse_args()

    if args.through:
        idx = THROUGH_ORDER.index(args.through)
        steps = STEPS[: idx + 1]
    else:
        steps = STEPS

    failed: list[str] = []
    for name, script in steps:
        path = ROOT / script
        if not path.is_file():
            print(f"[SKIP] {name}: missing {script}")
            failed.append(name)
            continue
        print(f"\n>>> Running {script} ({name})")
        proc = subprocess.run([PY, str(path)], cwd=API_ROOT)
        if proc.returncode != 0:
            failed.append(name)

    if failed:
        print(f"\n=== run_advisor_all FAILED at: {', '.join(failed)} ===")
        return 1
    print("\n=== run_advisor_all: ALL PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
