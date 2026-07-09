#!/usr/bin/env python3
"""CRM FINAL 验收：串联已完成的 verify_crm_*.py。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API_ROOT = ROOT.parent
PY = sys.executable

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from tests.verify_crm_helpers import check, finish_phase


def main() -> int:
    results: list[bool] = []
    r = subprocess.run([PY, str(ROOT / "run_crm_all.py"), "--through", "2f"], cwd=API_ROOT)
    results.append(check("VF-1 run_crm_all --through 2f", r.returncode == 0, str(r.returncode)))
    r2 = subprocess.run([PY, str(ROOT / "verify_crm_regression.py")], cwd=API_ROOT)
    results.append(check("VF-2 verify_crm_regression (RG-1/RG-2)", r2.returncode == 0, str(r2.returncode)))
    r3 = subprocess.run([PY, str(ROOT / "verify_crm_uat_f2.py")], cwd=API_ROOT)
    results.append(check("VF-3 verify_crm_uat_f2 (§6.2 API)", r3.returncode == 0, str(r3.returncode)))
    return finish_phase("FINAL", results)


if __name__ == "__main__":
    raise SystemExit(main())
