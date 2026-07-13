#!/usr/bin/env python3
"""运行 M0～M8 自动验收（TestClient + 发布门禁）。"""
from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(API_ROOT))
PY = sys.executable

os.environ["VERIFY_LIVE_API"] = "0"
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")

STEPS = [
    ("M0", "verify_m0.py"),
    ("M1", "verify_m1.py"),
    ("M2", "verify_m2.py"),
    ("M3", "verify_m3.py"),
    ("M4", "verify_m4.py"),
    ("M5", "verify_m5.py"),
    ("M6", "verify_m6.py"),
    ("M7", "verify_m7.py"),
    ("M8", "verify_m8.py"),
]


def restore_test_data() -> None:
    from app.database import SessionLocal
    from tests.test_helpers import restore_single_company_user

    db = SessionLocal()
    try:
        restore_single_company_user(db)
    finally:
        db.close()


def main() -> int:
    from tests.http_client import clear_sms_rate_limits, reset_all_tenant_quotas

    clear_sms_rate_limits()
    reset_all_tenant_quotas()
    restore_test_data()
    failed = []
    for name, script in STEPS:
        if name != "M0":
            restore_test_data()
        clear_sms_rate_limits()
        print(f"\n{'=' * 40}\n>>> {name}\n{'=' * 40}")
        r = subprocess.run([PY, "-B", str(ROOT / script)], cwd=API_ROOT)
        if r.returncode != 0:
            failed.append(name)
    print(f"\n{'=' * 40}")
    if failed:
        print("失败:", ", ".join(failed))
        return 1
    print("M0～M8 全部通过 — v0.3.3 发布门禁 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
