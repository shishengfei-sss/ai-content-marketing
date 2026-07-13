#!/usr/bin/env python3
"""v0.6 Phase D 验收：人格库种子、persona_service、orchestrator 注入与收束。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

API_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parent
PY = sys.executable

os.environ.setdefault("FORCE_FAKE_PLATFORM_LLM", "1")
os.environ["VERIFY_LIVE_API"] = "0"
sys.path.insert(0, str(API_ROOT))

from tests.alembic_head import EXPECTED_HEAD, is_at_expected_head
from tests.http_client import check

ORCH = API_ROOT / "app" / "services" / "agent" / "orchestrator.py"
MIGRATION = API_ROOT / "alembic" / "versions" / "033_persona_kb_seed.py"


def step_1d_seeds(results: list[bool]) -> None:
    from app.services.persona_seeds import PERSONA_KB_CHUNKS, PERSONA_KB_TITLE

    codes = [c["code"] for c in PERSONA_KB_CHUNKS]
    results.append(check("VA1d-1 人格库 9 条", len(PERSONA_KB_CHUNKS) == 9, str(len(codes))))
    results.append(
        check(
            "VA1d-2 编号 P-001～P-009",
            codes == [f"P-{i:03d}" for i in range(1, 10)],
            ", ".join(codes),
        )
    )
    required_fields = ("人格编号", "人格名称", "触发信号", "示例话术")
    missing = [
        item["code"]
        for item in PERSONA_KB_CHUNKS
        if not all(f in item["content"] for f in required_fields)
    ]
    results.append(check("VA1d-3 手册必填字段", not missing, ", ".join(missing)))
    results.append(check("VA1d-4 KB 标题", PERSONA_KB_TITLE == "营销顾问人格库", PERSONA_KB_TITLE))


def step_1d_service(results: list[bool]) -> None:
    from app.services.persona_service import (
        MIN_TURNS_FOR_PERSONA,
        CONVERGE_USER_TURNS,
        build_convergence_hint,
        build_persona_context,
        count_user_turns,
    )

    msgs = [
        SimpleNamespace(role="user", content="你好"),
        SimpleNamespace(role="assistant", content="您好"),
        SimpleNamespace(role="user", content="再想想"),
    ]
    results.append(check("VA1d-5 用户轮次计数", count_user_turns(msgs) == 2, ""))
    results.append(
        check(
            "VA1d-6 第3轮前不注入",
            build_persona_context(
                None,  # type: ignore[arg-type]
                tenant_id=None,  # type: ignore[arg-type]
                query="焦虑",
                user_turn_count=MIN_TURNS_FOR_PERSONA - 1,
            )
            == "",
            "",
        )
    )
    results.append(
        check(
            "VA1d-7 第10轮收束提示",
            "收束" in build_convergence_hint(CONVERGE_USER_TURNS),
            build_convergence_hint(CONVERGE_USER_TURNS)[:40],
        )
    )


def step_1d_orchestrator(results: list[bool]) -> None:
    text = ORCH.read_text(encoding="utf-8") if ORCH.is_file() else ""
    results.append(check("VA1d-8 orchestrator 导入 persona_service", "persona_service" in text, ""))
    results.append(check("VA1d-9 注入 build_persona_context", "build_persona_context" in text, ""))
    results.append(check("VA1d-10 收束 build_convergence_hint", "build_convergence_hint" in text, ""))
    results.append(check("VA1d-11 用户轮次字段", "用户轮次=" in text, ""))


def step_1d_migration(results: list[bool]) -> None:
    results.append(check("VA1d-12 033 迁移文件", MIGRATION.is_file(), str(MIGRATION)))
    results.append(check("VA1d-13 alembic head≥033", EXPECTED_HEAD >= "033", EXPECTED_HEAD))
    proc = subprocess.run(
        [PY, "-m", "alembic", "current"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    results.append(check("VA1d-14 数据库已升级 033", is_at_expected_head(out), out.strip()[:120]))

    if not is_at_expected_head(out):
        return

    from app.database import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT chunk_count FROM knowledge_documents "
                "WHERE title = '营销顾问人格库' AND scope = 'platform'"
            )
        ).fetchone()
        results.append(
            check(
                "VA1d-15 平台人格库文档",
                row is not None and int(row[0]) >= 9,
                str(row[0] if row else None),
            )
        )
        if row:
            cnt = db.execute(
                text(
                    "SELECT COUNT(*) FROM knowledge_chunks k "
                    "JOIN knowledge_documents d ON d.id = k.document_id "
                    "WHERE d.title = '营销顾问人格库' AND k.content LIKE '%人格编号%'"
                )
            ).scalar()
            results.append(check("VA1d-16 人格 chunks", int(cnt or 0) >= 9, str(cnt)))
    finally:
        db.close()


def main() -> int:
    results: list[bool] = []
    step_1d_seeds(results)
    step_1d_service(results)
    step_1d_orchestrator(results)
    step_1d_migration(results)

    passed = sum(results)
    total = len(results)
    print(f"\n=== verify_advisor_1d: {passed}/{total} PASS ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
