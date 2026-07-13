#!/usr/bin/env python3
"""v0.6 Phase A 验收：需求规格 §3.19 / 执行计划落盘（docs/v0.6-advisor执行计划.md）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs"
SRS = DOCS / "需求规格.md"
PLAN = DOCS / "v0.6-advisor执行计划.md"
AGENT_TC = DOCS / "智能体测试用例.md"

STEPS = {
    "0a-1": "需求规格含 FR-ADVISOR 与 §3.19",
    "0a-2": "v0.6-advisor执行计划.md 存在",
    "0a-3": "§3.19.3 提示词条文与 §6.7 TADV 用例",
    "0a-4": "智能体测试用例含 TADV 映射",
}


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{mark}] {label}{suffix}")
    return ok


def step_0a_1(results: list[bool]) -> None:
    text = SRS.read_text(encoding="utf-8") if SRS.is_file() else ""
    results.append(check("0a-1-1 文档版本 v0.6+", "v0.6.0" in text[:800] or "v0.6.1" in text[:800]))
    results.append(check("0a-1-2 §3.19 FR-ADVISOR", "### 3.19" in text and "FR-ADVISOR" in text))
    results.append(check("0a-1-3 §6.6 执行计划", "### 6.6" in text and "Phase B" in text))
    results.append(check("0a-1-4 §6.7 测试用例 TADV", "### 6.7" in text and "TADV-CFG-01" in text))
    results.append(check("0a-1-5 修订记录 v0.6+", "| **v0.6.0**" in text or "| **v0.6.1**" in text))


def step_0a_2(results: list[bool]) -> None:
    results.append(check("0a-2-1 执行计划文件", PLAN.is_file()))
    if PLAN.is_file():
        plan = PLAN.read_text(encoding="utf-8")
        results.append(check("0a-2-2 含 verify_advisor_0a", "verify_advisor_0a.py" in plan))
        results.append(check("0a-2-3 含 Phase B 032", "032" in plan and "universal_advisor" in plan))


def step_0a_3(results: list[bool]) -> None:
    text = SRS.read_text(encoding="utf-8") if SRS.is_file() else ""
    keywords = [
        "通用营销创作顾问",
        "我不回答",
        "input_class",
        "prompt_builder",
        "welcome_message",
    ]
    missing = [k for k in keywords if k not in text]
    results.append(check("0a-3-1 §3.19.3 核心条文", not missing, ", ".join(missing)))


def step_0a_4(results: list[bool]) -> None:
    text = AGENT_TC.read_text(encoding="utf-8") if AGENT_TC.is_file() else ""
    results.append(check("0a-4-1 TADV 映射节", "TADV" in text or "§6.7" in text, "见需求规格 §6.7"))


def main() -> int:
    parser = argparse.ArgumentParser(description="v0.6 Phase A doc verification")
    parser.add_argument("--step", choices=list(STEPS.keys()), help="Run single step")
    args = parser.parse_args()

    results: list[bool] = []
    runners = {
        "0a-1": step_0a_1,
        "0a-2": step_0a_2,
        "0a-3": step_0a_3,
        "0a-4": step_0a_4,
    }
    if args.step:
        runners[args.step](results)
    else:
        for fn in runners.values():
            fn(results)

    passed = sum(results)
    total = len(results)
    print(f"\n=== verify_advisor_0a: {passed}/{total} PASS ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
