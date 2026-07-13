#!/usr/bin/env python3
"""运行 Agent T0 + A0～A1 自动验收（后续扩展至 AG8）。"""
from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parent
PY = sys.executable
sys.path.insert(0, str(API_ROOT))

# 全量离线验收：TestClient + FakeLLM（勿连 live API，避免端口 8003 旧代码干扰）
os.environ["VERIFY_LIVE_API"] = "0"
os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")

from tests.http_client import reset_all_tenant_quotas, reset_test_client, clear_sms_rate_limits

STEPS = [
    ("T0", "verify_t0.py"),
    ("A0", "verify_a0.py"),
    ("A1", "verify_a1.py"),
    ("A2", "verify_a2.py"),
    ("A3", "verify_a3.py"),
    ("B1", "verify_b1.py"),
    ("B2", "verify_b2.py"),
    ("B3", "verify_b3.py"),
    ("B4", "verify_b4.py"),
    ("LM1", "verify_lm1.py"),
    ("LM2", "verify_lm2.py"),
    ("LM3", "verify_lm3.py"),
    ("LM4", "verify_lm4.py"),
    ("LM5", "verify_lm5.py"),
    ("C1", "verify_c1.py"),
    ("C2", "verify_c2.py"),
    ("C3", "verify_c3.py"),
    ("C4", "verify_c4.py"),
    ("C5", "verify_c5.py"),
    ("C6", "verify_c6.py"),
    ("WF1", "verify_wf_ui.py"),
    ("WF2", "verify_wf2.py"),
    ("WF3", "verify_wf3.py"),
    ("VP1", "verify_preflight.py"),
    ("MM1", "verify_memory_mgmt.py"),
    ("VPC1", "verify_proposal_count.py"),
    ("AG8", "verify_ag8.py"),
]


def main() -> int:
    reset_test_client()
    reset_all_tenant_quotas()
    clear_sms_rate_limits()
    failed = []
    for name, script in STEPS:
        print(f"\n{'=' * 40}\n>>> {name}\n{'=' * 40}")
        r = subprocess.run([PY, "-B", str(ROOT / script)], cwd=API_ROOT)
        if r.returncode != 0:
            failed.append(name)
    print(f"\n{'=' * 40}")
    if failed:
        print("失败:", ", ".join(failed))
        return 1
    print("T0 + A0～A3 + B1～B4 + LM1～LM5 + C1～C6 + AG8 全部通过 — v0.4 Agent 里程碑完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
