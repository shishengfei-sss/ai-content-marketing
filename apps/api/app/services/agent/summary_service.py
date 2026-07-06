"""Agent 会话摘要与 recall（LM2）。"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import AgentMemoryFact, AgentSessionSummary
from app.services.agent.session_service import get_session, list_messages
from app.services.embedding_service import cosine_similarity, embed_text
from app.services.llm.base import LLMMessage
from app.services.llm_service import llm_service

SUMMARY_SYSTEM_PROMPT = """你是营销创作会话摘要助手。根据对话记录输出 JSON：
{"summary":"100字内中文摘要","topics":["主题1","主题2"]}
仅输出 JSON，无 markdown。"""


def _extract_topics(raw: str) -> tuple[str, list[str]]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
    try:
        data = json.loads(text)
        summary = str(data.get("summary") or "").strip()
        topics = [str(t).strip() for t in (data.get("topics") or []) if str(t).strip()]
        if summary:
            return summary, topics
    except json.JSONDecodeError:
        pass
    return raw.strip()[:500], []


def _topics_to_json(topics: list[str]) -> str | None:
    if not topics:
        return None
    return json.dumps(topics, ensure_ascii=False)


async def generate_session_summary(
    db: Session,
    ctx: TenantContext,
    session_id: UUID,
    *,
    llm_source: str = "platform",
) -> AgentSessionSummary:
    session = get_session(db, session_id, tenant_id=ctx.tenant_id, user_id=ctx.user.id)
    messages = list_messages(db, session_id)
    if not messages:
        raise HTTPException(status_code=400, detail="会话暂无消息，无法生成摘要")

    convo = "\n".join(f"{m.role}: {m.content}" for m in messages[-20:])
    llm_messages = [
        LLMMessage(role="system", content=SUMMARY_SYSTEM_PROMPT),
        LLMMessage(role="user", content=f"会话标题：{session.title}\n\n对话：\n{convo}"),
    ]
    try:
        result = await llm_service.chat(
            db,
            ctx.tenant_id,
            llm_messages,
            llm_source=llm_source,
            check_platform_quota=False,
        )
    except ValueError as e:
        from app.services.content_generation_service import raise_llm_config_error

        raise_llm_config_error(e)

    summary_text, topics = _extract_topics(result.content)
    if not summary_text:
        raise HTTPException(status_code=502, detail="摘要生成失败")

    existing = (
        db.query(AgentSessionSummary)
        .filter(uuid_eq(AgentSessionSummary.session_id, session_id))
        .first()
    )
    if existing:
        existing.summary_text = summary_text
        existing.topics_json = _topics_to_json(topics)
        existing.message_count = len(messages)
        db.commit()
        db.refresh(existing)
        return existing

    row = AgentSessionSummary(
        session_id=session_id,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        summary_text=summary_text,
        topics_json=_topics_to_json(topics),
        message_count=len(messages),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_session_summary(
    db: Session,
    ctx: TenantContext,
    session_id: UUID,
) -> AgentSessionSummary:
    get_session(db, session_id, tenant_id=ctx.tenant_id, user_id=ctx.user.id)
    summary = (
        db.query(AgentSessionSummary)
        .filter(
            uuid_eq(AgentSessionSummary.session_id, session_id),
            uuid_eq(AgentSessionSummary.tenant_id, ctx.tenant_id),
            uuid_eq(AgentSessionSummary.user_id, ctx.user.id),
        )
        .first()
    )
    if not summary:
        raise HTTPException(status_code=404, detail="会话摘要不存在")
    return summary


def _token_overlap_score(text: str, query: str) -> float:
    if not query.strip() or not text.strip():
        return 0.0
    q = query.strip().lower()
    t = text.lower()
    score = 0.0
    if q in t:
        score += 3.0
    for token in q.replace("，", " ").replace("。", " ").split():
        if len(token) >= 2 and token in t:
            score += 1.0
    for i in range(len(q) - 1):
        gram = q[i : i + 2]
        if gram in t:
            score += 0.25
    return score


def _hybrid_text_score(text: str, query: str) -> float:
    overlap = _token_overlap_score(text, query)
    if not text.strip() or not query.strip():
        return overlap
    vec = cosine_similarity(embed_text(text), embed_text(query)) * 5.0
    return overlap + vec


def recall_memories(
    db: Session,
    ctx: TenantContext,
    *,
    query: str,
    limit: int = 10,
    mode: str = "keyword",
) -> dict:
    q = query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="query 不能为空")
    limit = max(1, min(limit, 30))
    pattern = f"%{q}%"

    if mode == "hybrid":
        all_summaries = (
            db.query(AgentSessionSummary)
            .filter(
                uuid_eq(AgentSessionSummary.tenant_id, ctx.tenant_id),
                uuid_eq(AgentSessionSummary.user_id, ctx.user.id),
            )
            .order_by(AgentSessionSummary.updated_at.desc())
            .limit(50)
            .all()
        )
        summaries = sorted(
            all_summaries,
            key=lambda s: _hybrid_text_score(s.summary_text, q),
            reverse=True,
        )
        summaries = [s for s in summaries if _hybrid_text_score(s.summary_text, q) > 0][:limit]

        fact_query = (
            db.query(AgentMemoryFact)
            .filter(AgentMemoryFact.is_confirmed.is_(True))
            .filter(
                (AgentMemoryFact.scope == "user") & uuid_eq(AgentMemoryFact.user_id, ctx.user.id)
                | ((AgentMemoryFact.scope == "tenant") & uuid_eq(AgentMemoryFact.tenant_id, ctx.tenant_id))
            )
        )
        all_facts = fact_query.order_by(AgentMemoryFact.updated_at.desc()).limit(50).all()
        facts = sorted(
            all_facts,
            key=lambda f: _hybrid_text_score(f.fact_text, q),
            reverse=True,
        )
        facts = [f for f in facts if _hybrid_text_score(f.fact_text, q) > 0][:limit]
        return {"query": q, "session_summaries": summaries, "memory_facts": facts, "mode": mode}

    summaries = (
        db.query(AgentSessionSummary)
        .filter(
            uuid_eq(AgentSessionSummary.tenant_id, ctx.tenant_id),
            uuid_eq(AgentSessionSummary.user_id, ctx.user.id),
            AgentSessionSummary.summary_text.ilike(pattern),
        )
        .order_by(AgentSessionSummary.updated_at.desc())
        .limit(limit)
        .all()
    )

    user_facts = (
        db.query(AgentMemoryFact)
        .filter(
            AgentMemoryFact.scope == "user",
            uuid_eq(AgentMemoryFact.user_id, ctx.user.id),
            AgentMemoryFact.is_confirmed.is_(True),
            AgentMemoryFact.fact_text.ilike(pattern),
        )
        .order_by(AgentMemoryFact.updated_at.desc())
        .limit(limit)
        .all()
    )
    tenant_facts = (
        db.query(AgentMemoryFact)
        .filter(
            AgentMemoryFact.scope == "tenant",
            uuid_eq(AgentMemoryFact.tenant_id, ctx.tenant_id),
            AgentMemoryFact.is_confirmed.is_(True),
            AgentMemoryFact.fact_text.ilike(pattern),
        )
        .order_by(AgentMemoryFact.updated_at.desc())
        .limit(limit)
        .all()
    )

    seen: set[UUID] = set()
    facts: list[AgentMemoryFact] = []
    for item in user_facts + tenant_facts:
        if item.id in seen:
            continue
        seen.add(item.id)
        facts.append(item)
        if len(facts) >= limit:
            break

    return {
        "query": q,
        "session_summaries": summaries,
        "memory_facts": facts,
        "mode": mode,
    }
