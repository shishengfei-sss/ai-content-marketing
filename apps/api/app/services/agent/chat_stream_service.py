"""Agent Chat SSE 流式响应（B4）。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AgentSession, Content, User
from app.schemas import AgentChatResponse, ContentGenerateRequest, ContentProposalsRequest
from app.services.agent.chat_service import _content_out, _last_proposals_from_session, _resolve_content_format
from app.services.agent.intent_parser import parse_intent
from app.services.agent.session_service import append_message, effective_advisor_code
from app.services.agent.sse import format_sse
from app.services.assistant_service import get_profile, normalize_advisor_code, require_active_assistant
from app.services.content_generation_service import (
    raise_llm_config_error,
    run_generate_proposals,
    validate_content_params,
)
from app.services.content_service import get_content_for_tenant
from app.services.knowledge_service import get_brand_profile, get_template, get_user_prompt, search_knowledge
from app.services.llm.base import LLMMessage
from app.services.llm_service import llm_service
from app.services.platform_llm_service import consume_platform_quota
from app.services.prompt_builder import build_system_prompt, build_user_prompt, default_content_format

logger = logging.getLogger(__name__)

CHUNK_SIZE = 8


async def _yield_text_deltas(text: str) -> AsyncIterator[str]:
    for i in range(0, len(text), CHUNK_SIZE):
        yield format_sse("delta", {"text": text[i : i + CHUNK_SIZE]})


def _build_generate_messages(db: Session, tenant_id, user: User, body: ContentGenerateRequest):
    content_format = validate_content_params(
        body.platform,
        body.content_format or default_content_format(body.platform),
    )
    advisor_code = normalize_advisor_code(body.industry_code)
    require_active_assistant(db, advisor_code)
    assistant = get_profile(db, advisor_code)

    system_prompt = build_system_prompt(body.platform, content_format=content_format, assistant=assistant)
    template = get_template(db, advisor_code, body.platform, body.scene)
    rag_chunks = search_knowledge(
        db,
        tenant_id=tenant_id,
        industry_code=advisor_code,
        query=f"{body.topic} {body.scene}",
    )
    brand = get_brand_profile(db, tenant_id)
    user_prompt_profile = get_user_prompt(db, user.id) if body.apply_user_prompt else None
    proposal = body.selected_proposal

    user_prompt = build_user_prompt(
        platform=body.platform,
        scene=body.scene,
        topic=body.topic,
        content_format=content_format,
        scene_name=template.name if template else "",
        template_hint=template.prompt_hint if template else "",
        rag_snippets=[c.content for c in rag_chunks],
        brand_name=brand.company_display_name if brand else "",
        brand_tone=brand.tone if brand else "",
        brand_cta=brand.cta_text if brand else "",
        brand_sample=brand.sample_snippet if brand else "",
        user_instructions=user_prompt_profile.global_instructions if user_prompt_profile else "",
        ephemeral_instruction=body.ephemeral_instruction,
        selected_proposal_title=proposal.title if proposal else "",
        selected_proposal_angle=proposal.angle if proposal else "",
        selected_proposal_outline=proposal.outline if proposal else "",
    )
    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=user_prompt),
    ]
    return messages, content_format, proposal


async def stream_chat(
    db: Session,
    session: AgentSession,
    user: User,
    *,
    message: str,
    llm_source: str = "platform",
    selected_proposal_index: int | None = None,
) -> AsyncIterator[str]:
    append_message(db, session, role="user", content=message)

    try:
        intent = await parse_intent(
            db,
            session.tenant_id,
            message=message,
            industry_code=effective_advisor_code(session),
            llm_source=llm_source,
            selected_proposal_index=selected_proposal_index,
        )
    except HTTPException as exc:
        yield format_sse("error", {"detail": exc.detail})
        return

    if intent.action == "clarify" or (intent.action == "proposals" and not intent.platform):
        question = intent.clarify_question or "请问要发布到哪个平台？主题是什么？"
        async for evt in _yield_text_deltas(question):
            yield evt
        assistant = append_message(db, session, role="assistant", content=question, message_type="clarify")
        resp = AgentChatResponse(
            action="clarify",
            assistant_message=question,
            clarify_question=question,
            message_id=assistant.id,
        )
        yield format_sse("done", resp.model_dump(mode="json"))
        return

    if intent.action in ("proposals", "generate"):
        if not intent.platform:
            question = intent.clarify_question or "请问要发布到哪个平台？"
            async for evt in _yield_text_deltas(question):
                yield evt
            assistant = append_message(db, session, role="assistant", content=question, message_type="clarify")
            resp = AgentChatResponse(
                action="clarify",
                assistant_message=question,
                clarify_question=question,
                message_id=assistant.id,
            )
            yield format_sse("done", resp.model_dump(mode="json"))
            return
        fmt = _resolve_content_format(intent, intent.platform)
        validate_content_params(intent.platform, fmt)

    if intent.action == "proposals":
        topic = intent.topic or message[:200]
        req = ContentProposalsRequest(
            industry_code=effective_advisor_code(session),
            platform=intent.platform,  # type: ignore[arg-type]
            scene=intent.scene or "brand_intro",
            topic=topic,
            content_format=_resolve_content_format(intent, intent.platform),  # type: ignore[arg-type]
            llm_source=llm_source,
        )
        result = await run_generate_proposals(db, session.tenant_id, req)
        summary = f"已生成 {len(result.proposals)} 个选题方案，请选择其一继续生成正文。"
        async for evt in _yield_text_deltas(summary):
            yield evt
        meta = {"proposals": [p.model_dump() for p in result.proposals]}
        assistant = append_message(
            db,
            session,
            role="assistant",
            content=summary,
            message_type="proposals",
            metadata=meta,
        )
        resp = AgentChatResponse(
            action="proposals",
            assistant_message=summary,
            proposals=result.proposals,
            message_id=assistant.id,
        )
        yield format_sse("done", resp.model_dump(mode="json"))
        return

    if intent.action == "generate":
        proposals = _last_proposals_from_session(db, session.id)
        idx = intent.selected_proposal_index if intent.selected_proposal_index is not None else 0
        if not proposals:
            question = "请先生成选题方案，或指定要使用的方案。"
            async for evt in _yield_text_deltas(question):
                yield evt
            assistant = append_message(db, session, role="assistant", content=question, message_type="clarify")
            resp = AgentChatResponse(
                action="clarify",
                assistant_message=question,
                clarify_question=question,
                message_id=assistant.id,
            )
            yield format_sse("done", resp.model_dump(mode="json"))
            return
        if idx < 0 or idx >= len(proposals):
            yield format_sse("error", {"detail": "方案索引无效"})
            return
        selected = proposals[idx]
        topic = intent.topic or selected.title
        req = ContentGenerateRequest(
            industry_code=effective_advisor_code(session),
            platform=intent.platform or "wechat",  # type: ignore[arg-type]
            scene=intent.scene or "brand_intro",
            topic=topic,
            content_format=_resolve_content_format(intent, intent.platform or "wechat"),
            selected_proposal=selected,
            llm_source=llm_source,
        )
        messages, content_format, proposal = _build_generate_messages(db, session.tenant_id, user, req)
        parts: list[str] = []
        try:
            async for chunk in llm_service.stream(
                db,
                session.tenant_id,
                messages,
                llm_source=llm_source,
                check_platform_quota=True,
            ):
                parts.append(chunk)
                yield format_sse("delta", {"text": chunk})
        except ValueError as e:
            raise_llm_config_error(e)
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("LLM stream generate failed")
            raise HTTPException(status_code=502, detail=f"生成失败: {e}") from e

        full_body = "".join(parts)
        topic_title = proposal.title if proposal else req.topic
        cfg = llm_service.resolve_config(db, session.tenant_id, llm_source)
        content = Content(
            tenant_id=session.tenant_id,
            author_id=user.id,
            industry_code=req.industry_code,
            platform=req.platform,
            scene=req.scene,
            topic=topic_title,
            body=full_body,
            content_format=content_format,
            status="draft",
            llm_provider=cfg.provider,
            llm_model=cfg.model,
        )
        db.add(content)
        if llm_source == "platform":
            consume_platform_quota(db, session.tenant_id)
        db.commit()
        db.refresh(content)
        content = get_content_for_tenant(db, content.id, session.tenant_id)

        summary = f"正文已生成：《{content.topic}》"
        assistant = append_message(
            db,
            session,
            role="assistant",
            content=summary,
            message_type="content",
            metadata={"content_id": str(content.id)},
        )
        resp = AgentChatResponse(
            action="generate",
            assistant_message=summary,
            content=_content_out(content),
            message_id=assistant.id,
        )
        yield format_sse("done", resp.model_dump(mode="json"))
        return

    reply = intent.clarify_question or "我可以帮您生成营销内容方案或正文，请告诉我平台和主题。"
    async for evt in _yield_text_deltas(reply):
        yield evt
    assistant = append_message(db, session, role="assistant", content=reply, message_type="text")
    resp = AgentChatResponse(
        action="chat",
        assistant_message=reply,
        message_id=assistant.id,
    )
    yield format_sse("done", resp.model_dump(mode="json"))
