#!/usr/bin/env python3
"""v0.6.1 Phase F 验收：合规自检（TADV-KB-03 / FR-ADVISOR-20）。

覆盖：
- system prompt 含合规自检条款
- parse_compliance_marks 解析 warn/block
- 无违禁时不追加标记
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ["VERIFY_LIVE_API"] = "0"

from tests.http_client import check

from app.services.prompt_builder import (
    COMPLIANCE_SELF_CHECK_BLOCK,
    build_system_prompt,
    parse_compliance_marks,
)


def step_compliance_prompt(results: list[bool]) -> None:
    """FR-ADVISOR-20: system prompt 含合规自检条款。"""
    prompt = build_system_prompt("wechat")
    results.append(check("VAC-1 prompt 含合规自检", "合规自检" in prompt, ""))
    results.append(check("VAC-2 prompt 含「保证涨粉」禁例", "保证涨粉" in prompt, ""))
    results.append(check("VAC-3 prompt 含 COMPLIANCE_BLOCK 标记说明", "COMPLIANCE_BLOCK" in prompt, ""))


def step_compliance_parse(results: list[bool]) -> None:
    """parse_compliance_marks 解析。"""
    clean, mark = parse_compliance_marks("正文内容\n[COMPLIANCE_WARN] 含违禁表述")
    results.append(check("VAC-4 warn 标记解析", mark == "warn", str(mark)))
    results.append(check("VAC-5 warn 剥离标记行", "[COMPLIANCE" not in clean, clean[-40:]))

    clean2, mark2 = parse_compliance_marks("正文\n[COMPLIANCE_BLOCK] 内容违规")
    results.append(check("VAC-6 block 标记解析", mark2 == "block", str(mark2)))
    results.append(check("VAC-7 block 剥离标记行", "[COMPLIANCE" not in clean2, clean2[-40:]))

    clean3, mark3 = parse_compliance_marks("正常正文，无违禁")
    results.append(check("VAC-8 无违禁 mark=None", mark3 is None, str(mark3)))
    results.append(check("VAC-9 无违禁 body 不变", clean3 == "正常正文，无违禁", ""))


def main() -> int:
    results: list[bool] = []
    step_compliance_prompt(results)
    step_compliance_parse(results)

    passed = sum(results)
    total = len(results)
    print(f"\n=== verify_advisor_compliance: {passed}/{total} PASS ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
