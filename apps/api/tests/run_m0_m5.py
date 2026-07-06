#!/usr/bin/env python3
"""运行 M0～M8 自动验收 — 请优先使用 run_m0_m8.py。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable

STEPS = [
    ("M0", "verify_m0.py"),
    ("M1", "verify_m1.py"),
    ("M2", "verify_m2.py"),
    ("M3", "verify_m3.py"),
    ("M4", "verify_m4.py"),
    ("M5", "verify_m5.py"),
    ("M6", "verify_m6.py"),
    ("M7", "verify_m7.py"),
]


def main() -> int:
    failed = []
    for name, script in STEPS:
        print(f"\n{'=' * 40}\n>>> {name}\n{'=' * 40}")
        r = subprocess.run([PY, str(ROOT / script)], cwd=ROOT.parent)
        if r.returncode != 0:
            failed.append(name)
    print(f"\n{'=' * 40}")
    if failed:
        print("失败:", ", ".join(failed))
        return 1
    print("M0～M7 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())