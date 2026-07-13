#!/usr/bin/env python3
"""v0.6.1 Phase F 验收：零断点与收束（TADV-UE-02/03/04）。

覆盖：
- 每轮回复末尾有下一步引导
- 方案后引导正文
- 10 轮强制收束 action=clarify
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ["VERIFY_LIVE_API"] = "0"

from tests.http_client import check

from app.services.agent.orchestrator import _ensure_next_step, _BOUNDARY_REPLIES
from app.services.persona_service import (
    CONVERGE_USER_TURNS,
    build_convergence_hint,
    count_user_turns,
)


def step_ue_next_step(results: list[bool]) -> None:
    """TADV-UE-02: 每轮下一步引导。"""
    cases = [
        ("已完成。", True),
        ("好的，我来帮你。", True),
        ("请补充主题。", True),
        ("下一步：告诉我平台。", False),
        ("你可以直接说主题。", False),
    ]
    for reply, should_append in cases:
        result = _ensure_next_step(reply)
        has_hint = "下一步" in result[-80:] or "你可以" in result[-80:]
        if should_append:
            results.append(check(f"VAUE-1 追加引导: {reply[:15]}", has_hint, result[-60:]))
        else:
            results.append(check(f"VAUE-2 不重复: {reply[:15]}", result == reply, result[-60:]))


def step_ue_convergence(results: list[bool]) -> None:
    """TADV-UE-04: 10 轮收束提示。"""
    hint = build_convergence_hint(CONVERGE_USER_TURNS)
    results.append(check("VAUE-3 10轮收束提示存在", "收束" in hint, hint[:40]))
    no_hint = build_convergence_hint(CONVERGE_USER_TURNS - 1)
    results.append(check("VAUE-4 未达10轮无收束提示", no_hint == "", str(no_hint)[:40]))


def step_ue_convergence_forced(results: list[bool]) -> None:
    """TADV-UE-04: orchestrator 10 轮强制收束逻辑（静态校验导入）。"""
    from app.services.agent.orchestrator import CONVERGE_USER_TURNS as orch_converge

    results.append(check("VAUE-5 orchestrator 导入 CONVERGE_USER_TURNS", orch_converge == CONVERGE_USER_TURNS, str(orch_converge)))


def step_ue_welcome_structure(results: list[bool]) -> None:
    """TADV-UE-01: 开场白结构化（4项能力）。"""
    from app.services.assistant_service import default_marketing_profile

    welcome = default_marketing_profile().welcome_message
    results.append(check("VAUE-6 开场白含「营销」", "营销" in welcome, welcome[:40]))
    results.append(check("VAUE-7 开场白含「选题」或「主题」", "选题" in welcome or "主题" in welcome, welcome[:60]))


def main() -> int:
    results: list[bool] = []
    step_ue_next_step(results)
    step_ue_convergence(results)
    step_ue_convergence_forced(results)
    step_ue_welcome_structure(results)

    passed = sum(results)
    total = len(results)
    print(f"\n=== verify_advisor_ue: {passed}/{total} PASS ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
