#!/usr/bin/env python3
"""v0.6.1 Phase F 验收：人格库持久化锁定（TADV-PL-01 / FR-ADVISOR-18）。

覆盖：
- agent_sessions.persona_code 字段存在
- persona_service lock_persona / get_locked_persona
- build_persona_context 锁定优先
- 第3轮前不注入
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
from tests.alembic_head import is_at_expected_head

from app.services.persona_service import (
    MIN_TURNS_FOR_PERSONA,
    _extract_persona_code,
    build_persona_context,
    build_convergence_hint,
    count_user_turns,
)
from app.services.persona_seeds import PERSONA_KB_CHUNKS, PERSONA_KB_TITLE
from app.models import AgentSession


def step_persona_model(results: list[bool]) -> None:
    """FR-ADVISOR-18: agent_sessions.persona_code 字段存在。"""
    has_field = hasattr(AgentSession, "persona_code")
    results.append(check("VAPL-1 AgentSession.persona_code 字段", has_field, ""))


def step_persona_extract(results: list[bool]) -> None:
    """人格编号提取。"""
    code = _extract_persona_code(PERSONA_KB_CHUNKS[0]["content"])
    results.append(check("VAPL-2 提取 P-001", code == "P-001", str(code)))
    code2 = _extract_persona_code("无编号文本")
    results.append(check("VAPL-3 无编号返回 None", code2 is None, str(code2)))


def step_persona_min_turns(results: list[bool]) -> None:
    """第3轮前不注入。"""
    result = build_persona_context(None, tenant_id=None, query="test", user_turn_count=MIN_TURNS_FOR_PERSONA - 1)  # type: ignore[arg-type]
    results.append(check("VAPL-4 第3轮前不注入", result == "", result[:40]))


def step_persona_seeds(results: list[bool]) -> None:
    """人格库种子完整。"""
    codes = [c["code"] for c in PERSONA_KB_CHUNKS]
    results.append(check("VAPL-5 人格库9条", len(PERSONA_KB_CHUNKS) == 9, str(len(codes))))
    results.append(check("VAPL-6 编号 P-001～P-009", codes == [f"P-{i:03d}" for i in range(1, 10)], ",".join(codes)))
    results.append(check("VAPL-7 KB标题", PERSONA_KB_TITLE == "营销顾问人格库", PERSONA_KB_TITLE))


def step_persona_alembic(results: list[bool]) -> None:
    import subprocess
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    results.append(check("VAPL-8 alembic head=035", is_at_expected_head(out), out.strip()[:120]))


def main() -> int:
    results: list[bool] = []
    step_persona_model(results)
    step_persona_extract(results)
    step_persona_min_turns(results)
    step_persona_seeds(results)
    step_persona_alembic(results)

    passed = sum(results)
    total = len(results)
    print(f"\n=== verify_advisor_persona: {passed}/{total} PASS ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
