"""长期记忆注入与 token 预算（LM3）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import AgentMemoryFact, AgentSessionSummary
from app.services.agent.summary_service import recall_memories

DEFAULT_MAX_CHARS = 2400


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def build_memory_context(
    db: Session,
    ctx: TenantContext,
    *,
    hint: str = "",
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    max_chars = max(200, min(max_chars, DEFAULT_MAX_CHARS * 2))
    lines: list[str] = []

    recent_summaries = (
        db.query(AgentSessionSummary)
        .filter(
            uuid_eq(AgentSessionSummary.tenant_id, ctx.tenant_id),
            uuid_eq(AgentSessionSummary.user_id, ctx.user.id),
        )
        .order_by(AgentSessionSummary.updated_at.desc())
        .limit(3)
        .all()
    )
    for item in recent_summaries:
        lines.append(f"[会话摘要] {item.summary_text}")

    if hint.strip():
        recalled = recall_memories(db, ctx, query=hint.strip()[:100], limit=5)
        for item in recalled["session_summaries"]:
            line = f"[相关摘要] {item.summary_text}"
            if line not in lines:
                lines.append(line)
        for item in recalled["memory_facts"]:
            scope_label = "用户" if item.scope == "user" else "企业"
            lines.append(f"[{scope_label}记忆] {item.fact_text}")
    else:
        user_facts = (
            db.query(AgentMemoryFact)
            .filter(
                AgentMemoryFact.scope == "user",
                uuid_eq(AgentMemoryFact.user_id, ctx.user.id),
                AgentMemoryFact.is_confirmed.is_(True),
            )
            .order_by(AgentMemoryFact.updated_at.desc())
            .limit(5)
            .all()
        )
        tenant_facts = (
            db.query(AgentMemoryFact)
            .filter(
                AgentMemoryFact.scope == "tenant",
                uuid_eq(AgentMemoryFact.tenant_id, ctx.tenant_id),
                AgentMemoryFact.is_confirmed.is_(True),
            )
            .order_by(AgentMemoryFact.updated_at.desc())
            .limit(5)
            .all()
        )
        for item in user_facts:
            lines.append(f"[用户记忆] {item.fact_text}")
        for item in tenant_facts:
            lines.append(f"[企业记忆] {item.fact_text}")

    if not lines:
        return ""
    body = "\n".join(lines)
    return _truncate(body, max_chars)


def truncate_text(text: str, max_chars: int) -> str:
    return _truncate(text, max_chars)


def format_memory_block(context: str, *, max_chars: int | None = None) -> str:
    if not context.strip():
        return ""
    block = f"【长期记忆】\n{context.strip()}\n"
    if max_chars is not None:
        block = _truncate(block, max_chars)
    return block
