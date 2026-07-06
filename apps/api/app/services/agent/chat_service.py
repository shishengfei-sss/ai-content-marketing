"""Agent Chat：意图解析 → proposals / generate。"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models import AgentSession, User
from app.schemas import (
    AgentChatResponse,
    ContentGenerateRequest,
    ContentOut,
    ContentProposal,
    ContentProposalsRequest,
)
from app.services.agent.intent_parser import ParsedIntent, parse_intent
from app.services.agent.memory_injection import build_memory_context, format_memory_block
from app.services.agent.session_service import append_message, list_messages
from app.services.content_generation_service import run_generate_content, run_generate_proposals
from app.services.prompt_builder import default_content_format


def _content_out(content) -> ContentOut:
    preview_url = None
    if content.preview_path:
        preview_url = f"/storage/published/{content.preview_path}"
    return ContentOut(
        id=content.id,
        platform=content.platform,
        scene=content.scene,
        topic=content.topic,
        body=content.body,
        content_format=getattr(content, "content_format", "article") or "article",
        status=content.status,
        llm_provider=content.llm_provider,
        llm_model=content.llm_model,
        scheduled_at=content.scheduled_at,
        published_at=content.published_at,
        publish_error=content.publish_error,
        mock_read_count=content.mock_read_count or 0,
        preview_url=preview_url,
        created_at=content.created_at,
        updated_at=content.updated_at,
        author_name=content.author.display_name if content.author else "",
    )


def _last_proposals_from_session(db: Session, session_id: UUID) -> list[ContentProposal] | None:
    for msg in reversed(list_messages(db, session_id)):
        if msg.role != "assistant" or msg.message_type != "proposals":
            continue
        if not msg.metadata_json:
            continue
        try:
            data = json.loads(msg.metadata_json)
            items = data.get("proposals") or []
            return [ContentProposal(**p) for p in items]
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return None


def _resolve_content_format(intent: ParsedIntent, platform: str) -> str:
    return intent.content_format or default_content_format(platform)


async def handle_chat(
    db: Session,
    session: AgentSession,
    user: User,
    *,
    message: str,
    llm_source: str = "platform",
    selected_proposal_index: int | None = None,
    tenant_ctx: TenantContext | None = None,
) -> AgentChatResponse:
    append_message(db, session, role="user", content=message)

    memory_block = ""
    if tenant_ctx is not None:
        memory_block = format_memory_block(
            build_memory_context(db, tenant_ctx, hint=message),
        )

    intent = await parse_intent(
        db,
        session.tenant_id,
        message=message,
        industry_code=session.industry_code,
        llm_source=llm_source,
        selected_proposal_index=selected_proposal_index,
        memory_context=memory_block,
    )

    if intent.action == "clarify" or (intent.action == "proposals" and not intent.platform):
        question = intent.clarify_question or "请问要发布到哪个平台？主题是什么？"
        assistant = append_message(
            db,
            session,
            role="assistant",
            content=question,
            message_type="clarify",
        )
        return AgentChatResponse(
            action="clarify",
            assistant_message=question,
            clarify_question=question,
            message_id=assistant.id,
        )

    if intent.action in ("proposals", "generate"):
        if not intent.platform:
            question = intent.clarify_question or "请问要发布到哪个平台？"
            assistant = append_message(db, session, role="assistant", content=question, message_type="clarify")
            return AgentChatResponse(
                action="clarify",
                assistant_message=question,
                clarify_question=question,
                message_id=assistant.id,
            )
        fmt = _resolve_content_format(intent, intent.platform)
        from app.services.content_generation_service import validate_content_params

        validate_content_params(intent.platform, fmt)

    if intent.action == "proposals":
        topic = intent.topic or message[:200]
        req = ContentProposalsRequest(
            industry_code=session.industry_code,
            platform=intent.platform,  # type: ignore[arg-type]
            scene=intent.scene or "bookkeeping_intro",
            topic=topic,
            content_format=_resolve_content_format(intent, intent.platform),  # type: ignore[arg-type]
            llm_source=llm_source,
        )
        result = await run_generate_proposals(db, session.tenant_id, req)
        summary = f"已生成 {len(result.proposals)} 个选题方案，请选择其一继续生成正文。"
        meta = {"proposals": [p.model_dump() for p in result.proposals]}
        assistant = append_message(
            db,
            session,
            role="assistant",
            content=summary,
            message_type="proposals",
            metadata=meta,
        )
        return AgentChatResponse(
            action="proposals",
            assistant_message=summary,
            proposals=result.proposals,
            message_id=assistant.id,
        )

    if intent.action == "generate":
        proposals = _last_proposals_from_session(db, session.id)
        idx = intent.selected_proposal_index
        if idx is None:
            idx = 0
        if not proposals:
            question = "请先生成选题方案，或指定要使用的方案。"
            assistant = append_message(db, session, role="assistant", content=question, message_type="clarify")
            return AgentChatResponse(
                action="clarify",
                assistant_message=question,
                clarify_question=question,
                message_id=assistant.id,
            )
        if idx < 0 or idx >= len(proposals):
            raise HTTPException(status_code=400, detail="方案索引无效")
        selected = proposals[idx]
        topic = intent.topic or selected.title
        req = ContentGenerateRequest(
            industry_code=session.industry_code,
            platform=intent.platform or "wechat",  # type: ignore[arg-type]
            scene=intent.scene or "bookkeeping_intro",
            topic=topic,
            content_format=_resolve_content_format(intent, intent.platform or "wechat"),
            selected_proposal=selected,
            llm_source=llm_source,
        )
        content = await run_generate_content(db, session.tenant_id, user, req)
        summary = f"正文已生成：《{content.topic}》"
        assistant = append_message(
            db,
            session,
            role="assistant",
            content=summary,
            message_type="content",
            metadata={"content_id": str(content.id)},
        )
        return AgentChatResponse(
            action="generate",
            assistant_message=summary,
            content=_content_out(content),
            message_id=assistant.id,
        )

    reply = intent.clarify_question or "我可以帮您生成营销内容方案或正文，请告诉我平台和主题。"
    assistant = append_message(db, session, role="assistant", content=reply, message_type="text")
    return AgentChatResponse(
        action="chat",
        assistant_message=reply,
        message_id=assistant.id,
    )
