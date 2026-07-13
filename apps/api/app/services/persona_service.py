"""人格库检索与对话注入（v0.6 Phase D / v0.6.1 持久化锁定）。"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AgentSession
from app.services.knowledge_service import search_knowledge_scored
from app.services.persona_seeds import PERSONA_KB_TITLE

logger = logging.getLogger(__name__)

MIN_TURNS_FOR_PERSONA = 3
CONVERGE_USER_TURNS = 10


def count_user_turns(messages) -> int:
    return sum(1 for m in messages if getattr(m, "role", None) == "user")


def search_persona_variants(
    db: Session,
    *,
    tenant_id: UUID,
    query: str,
    limit: int = 2,
) -> list[str]:
    """从平台人格库检索匹配变体（P-001～P-009）。"""
    hits = search_knowledge_scored(
        db,
        tenant_id=tenant_id,
        industry_code="marketing",
        query=f"人格库 {query}",
        limit=max(limit, 3),
        mode="keyword",
    )
    results: list[str] = []
    for hit in hits:
        text = hit.chunk.content or ""
        if "人格编号" not in text and "P-00" not in text:
            continue
        if text not in results:
            results.append(text)
        if len(results) >= limit:
            break
    return results


def _extract_persona_code(block: str) -> str | None:
    """从人格变体文本提取 P-xxx 编号。"""
    import re

    m = re.search(r"P-\d{3}", block)
    return m.group(0) if m else None


def lock_persona(db: Session, session: AgentSession, persona_block: str) -> str | None:
    """FR-ADVISOR-18: 将命中的人格变体锁定到 session.persona_code。"""
    code = _extract_persona_code(persona_block)
    if code and getattr(session, "persona_code", None) != code:
        session.persona_code = code
        db.commit()
        logger.info("persona locked: session=%s persona=%s", session.id, code)
    return code


def get_locked_persona(
    db: Session,
    *,
    tenant_id: UUID,
    persona_code: str,
) -> str | None:
    """读取已锁定的人格变体文本（按编号精确匹配）。"""
    hits = search_knowledge_scored(
        db,
        tenant_id=tenant_id,
        industry_code="marketing",
        query=f"人格编号 {persona_code}",
        limit=5,
        mode="keyword",
    )
    for hit in hits:
        text = hit.chunk.content or ""
        if persona_code in text and "人格编号" in text:
            return text
    return None


def build_persona_context(
    db: Session,
    *,
    tenant_id: UUID,
    query: str,
    user_turn_count: int,
    session: AgentSession | None = None,
) -> str:
    if user_turn_count < MIN_TURNS_FOR_PERSONA:
        return ""

    locked_code = getattr(session, "persona_code", None) if session else None
    if locked_code:
        locked_block = get_locked_persona(db, tenant_id=tenant_id, persona_code=locked_code)
        if locked_block:
            return (
                f"[人格库 · {PERSONA_KB_TITLE}] 已锁定人格变体 {locked_code}（稳定人格不变，仅调整表达方式）：\n"
                f"--- 锁定变体 ---\n{locked_block}"
            )

    variants = search_persona_variants(db, tenant_id=tenant_id, query=query, limit=2)
    if not variants:
        return ""

    if session and variants:
        lock_persona(db, session, variants[0])

    lines = [f"[人格库 · {PERSONA_KB_TITLE}] 根据用户语气匹配以下变体（稳定人格不变，仅调整表达方式）："]
    for idx, block in enumerate(variants, start=1):
        lines.append(f"--- 变体 {idx} ---\n{block}")
    return "\n".join(lines)


def build_convergence_hint(user_turn_count: int) -> str:
    if user_turn_count < CONVERGE_USER_TURNS:
        return ""
    return (
        "【会话收束】用户已连续多轮对话仍未进入创作主线。"
        "请用 clarify 或引导生成方案，避免无限陪聊；每轮结尾给出明确下一步。"
    )

