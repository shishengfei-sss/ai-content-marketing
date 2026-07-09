#!/usr/bin/env python3
"""串联 v0.5 CRM 验收脚本（见 docs/v0.5-crm执行计划.md）。"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parent
PY = sys.executable

# 全量离线验收使用 FakeLLM，与 run_agent_a_c.py 一致
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from tests.http_client import reset_all_tenant_quotas

STEPS: list[tuple[str, str]] = [
    ("M0", "verify_crm_m0.py"),
    ("1a", "verify_crm_1a.py"),
    ("1b", "verify_crm_1b.py"),
    ("1c", "verify_crm_1c.py"),
    ("2a", "verify_crm_2a.py"),
    ("2b", "verify_crm_2b.py"),
    ("2c", "verify_crm_2c.py"),
    ("2d", "verify_crm_2d.py"),
    ("2e", "verify_crm_2e.py"),
    ("2f", "verify_crm_2f.py"),
    ("FINAL", "verify_crm_final.py"),
]

THROUGH_ORDER = [name for name, _ in STEPS]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CRM verify scripts in order")
    parser.add_argument(
        "--through",
        choices=THROUGH_ORDER,
        help="Run scripts up to and including this phase (e.g. 1a, M0, FINAL)",
    )
    args = parser.parse_args()

    reset_all_tenant_quotas()

    if args.through:
        idx = THROUGH_ORDER.index(args.through)
        steps = STEPS[: idx + 1]
    else:
        steps = STEPS

    failed: list[str] = []
    missing: list[str] = []
    for name, script in steps:
        path = ROOT / script
        print(f"\n{'=' * 48}\n>>> CRM {name} ({script})\n{'=' * 48}")
        if not path.is_file():
            print(f"SKIP: {script} 尚未创建")
            missing.append(name)
            continue
        r = subprocess.run([PY, str(path)], cwd=API_ROOT)
        if r.returncode != 0:
            failed.append(name)

    print(f"\n{'=' * 48}")
    if missing:
        print("未创建脚本:", ", ".join(missing))
    if failed:
        print("失败阶段:", ", ".join(failed))
        return 1
    if missing and not args.through:
        print("部分脚本未创建；使用 --through <已完成阶段> 仅验收到该阶段")
        return 1
    print("CRM 验收全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
