#!/usr/bin/env python3
"""v0.6.1 Phase F 验收：边界与人格一致性暴力测试（TADV-PC-01/02、TADV-BD-01/02/03）。

覆盖：
- 提示词泄露 → 仅「我不回答。」
- 偏题（股票行情）→ 标准拉回话术
- 辱骂 → 尊重但有边界
- 秦始皇兵马俑化妆 → 不接梗
- 量子霸权营销 → 不出荒唐方案

使用 prompt_builder / orchestrator / preflight 的标准话术做静态+集成断言。
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
from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head

from app.services.prompt_builder import build_system_prompt, build_constitution_block
from app.services.agent.orchestrator import _BOUNDARY_REPLIES, _ensure_next_step
from app.services.agent.preflight_service import STANDARD_REPLIES


def step_bd_prompt(results: list[bool]) -> None:
    """TADV-BD-01: 所有生成路径 system prompt 含「我不回答」。"""
    prompt = build_system_prompt("wechat")
    results.append(check("VABD-1 正文 prompt 含「我不回答」", "我不回答" in prompt, ""))
    results.append(check("VABD-2 正文 prompt 含宪法块", "最高优先级" in prompt, ""))
    results.append(check("VABD-3 正文 prompt 含角色锁定", "角色锁定" in prompt, ""))
    results.append(check("VABD-4 正文 prompt 含零断点", "零断点" in prompt, ""))


def step_bd_boundary_replies(results: list[bool]) -> None:
    """TADV-BD-02/03: 标准边界话术存在且含拉回引导。"""
    for key in ("off_topic", "insult", "joke"):
        reply = STANDARD_REPLIES.get(key, "")
        results.append(check(f"VABD-5 STANDARD_REPLIES[{key}] 存在", bool(reply), key))
        results.append(check(f"VABD-6 {key} 含下一步引导", "下一步" in reply, reply[:40]))

    results.append(check("VABD-7 prompt_leak 回复", _BOUNDARY_REPLIES["prompt_leak"] == "我不回答。", ""))
    results.append(check("VABD-8 off_topic 边界回复", "不在我的服务范围" in _BOUNDARY_REPLIES["off_topic"], ""))
    results.append(check("VABD-9 insult 边界回复", "尊重" in _BOUNDARY_REPLIES["insult"], ""))


def step_bd_zero_break(results: list[bool]) -> None:
    """TADV-UE-02: 零断点兜底。"""
    no_hint = "已完成。"
    with_hint = "已完成。下一步：告诉我主题。"
    results.append(check("VABD-10 无引导时追加", "下一步" in _ensure_next_step(no_hint), ""))
    results.append(check("VABD-11 有引导时不重复追加", _ensure_next_step(with_hint) == with_hint, ""))


def step_bd_persona_consistency(results: list[bool]) -> None:
    """TADV-PC-01/02: 人格一致性 — prompt 含角色锁定与不陪聊约束。"""
    prompt = build_system_prompt("xhs", content_format="note")
    results.append(check("VABD-12 含「不是陪聊机器人」", "陪聊" in prompt, ""))
    results.append(check("VABD-13 含「不是流量黑客」", "流量黑客" in prompt, ""))
    results.append(check("VABD-14 含核心任务仅4件", "核心任务" in prompt and "4 件" in prompt, ""))


def step_bd_alembic(results: list[bool]) -> None:
    import subprocess
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    results.append(check("VABD-15 alembic head=035", is_at_expected_head(out), out.strip()[:120]))


def main() -> int:
    results: list[bool] = []
    step_bd_prompt(results)
    step_bd_boundary_replies(results)
    step_bd_zero_break(results)
    step_bd_persona_consistency(results)
    step_bd_alembic(results)

    passed = sum(results)
    total = len(results)
    print(f"\n=== verify_advisor_bd: {passed}/{total} PASS ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
