"""内容生成核心逻辑（proposals / generate），供 content 路由与 Agent 共用。"""

from __future__ import annotations

import logging
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Content, User
from app.schemas import ContentGenerateRequest, ContentProposal, ContentProposalsRequest, ContentProposalsResponse
from app.services.assistant_service import get_profile, require_active_assistant
from app.services.content_service import get_content_for_tenant
from app.services.knowledge_service import get_brand_profile, get_template, get_user_prompt, search_knowledge
from app.services.llm.base import LLMMessage
from app.services.llm_service import llm_service
from app.services.platform_llm_service import consume_platform_quota
from app.services.prompt_builder import (
    build_proposals_system_prompt,
    build_proposals_user_prompt,
    build_system_prompt,
    build_user_prompt,
    default_content_format,
    parse_proposals_json,
    validate_platform_format,
)
from app.services.proposal_count import resolve_proposal_count

logger = logging.getLogger(__name__)


def raise_llm_config_error(exc: ValueError) -> None:
    code = str(exc)
    if code == "LLM_TENANT_KEY_NOT_CONFIGURED":
        raise HTTPException(status_code=400, detail="请先在设置中配置我的 API Key") from exc
    if code == "LLM_PLATFORM_NOT_CONFIGURED":
        raise HTTPException(status_code=400, detail="平台 AI 未配置，请使用我的 API Key 或联系管理员") from exc
    if code == "INVALID_LLM_SOURCE":
        raise HTTPException(status_code=400, detail="无效的 AI 来源") from exc
    if code == "LLM_API_KEY_NOT_CONFIGURED":
        raise HTTPException(status_code=400, detail="请先配置 AI 模型 API Key") from exc
    raise exc


def validate_content_params(platform: str, content_format: str) -> str:
    fmt = content_format or default_content_format(platform)
    try:
        validate_platform_format(platform, fmt)
    except ValueError as e:
        if str(e) == "INVALID_PLATFORM_FORMAT":
            raise HTTPException(status_code=400, detail="该平台不支持所选内容形态") from e
        raise
    return fmt


async def run_generate_proposals(
    db: Session,
    tenant_id: UUID,
    body: ContentProposalsRequest,
) -> ContentProposalsResponse:
    content_format = validate_content_params(body.platform, body.content_format or default_content_format(body.platform))
    require_active_assistant(db, body.industry_code)
    assistant = get_profile(db, body.industry_code)

    template = get_template(db, body.industry_code, body.platform, body.scene)
    system_prompt = build_proposals_system_prompt(assistant=assistant)
    user_prompt = build_proposals_user_prompt(
        platform=body.platform,
        scene=body.scene,
        topic=body.topic,
        content_format=content_format,
        scene_name=template.name if template else "",
        template_hint=template.prompt_hint if template else "",
        proposal_count=resolve_proposal_count(
            explicit=body.proposal_count,
            text=body.topic,
        ),
    )
    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=user_prompt),
    ]

    try:
        result = await llm_service.chat(
            db,
            tenant_id,
            messages,
            llm_source=body.llm_source,
            check_platform_quota=True,
        )
        raw_items = parse_proposals_json(
            result.content,
            proposal_count=resolve_proposal_count(
                explicit=body.proposal_count,
                text=body.topic,
            ),
        )
    except ValueError as e:
        if str(e) == "PROPOSALS_PARSE_FAILED":
            raise HTTPException(status_code=502, detail="方案生成失败，请重试") from e
        raise_llm_config_error(e)
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        logger.exception("LLM proposals request failed")
        raise HTTPException(status_code=502, detail="模型连接失败，请检查 API Key 与网络") from e
    except Exception as e:
        logger.exception("LLM proposals request failed")
        raise HTTPException(status_code=502, detail=f"方案生成失败: {e}") from e

    proposals = [ContentProposal(**item) for item in raw_items]
    return ContentProposalsResponse(proposals=proposals)


async def run_generate_content(
    db: Session,
    tenant_id: UUID,
    user: User,
    body: ContentGenerateRequest,
) -> Content:
    content_format = validate_content_params(body.platform, body.content_format or default_content_format(body.platform))
    require_active_assistant(db, body.industry_code)
    assistant = get_profile(db, body.industry_code)

    system_prompt = build_system_prompt(body.platform, content_format=content_format, assistant=assistant)
    template = get_template(db, body.industry_code, body.platform, body.scene)
    rag_chunks = search_knowledge(
        db,
        tenant_id=tenant_id,
        industry_code=body.industry_code,
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

    try:
        result = await llm_service.chat(
            db,
            tenant_id,
            messages,
            llm_source=body.llm_source,
            check_platform_quota=True,
        )
    except ValueError as e:
        raise_llm_config_error(e)
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        logger.exception("LLM request failed")
        raise HTTPException(status_code=502, detail="模型连接失败，请检查 API Key 与网络") from e
    except Exception as e:
        logger.exception("LLM request failed")
        raise HTTPException(status_code=502, detail=f"生成失败: {e}") from e

    topic = proposal.title if proposal else body.topic
    content = Content(
        tenant_id=tenant_id,
        author_id=user.id,
        industry_code=body.industry_code,
        platform=body.platform,
        scene=body.scene,
        topic=topic,
        body=result.content,
        content_format=content_format,
        status="draft",
        llm_provider=result.provider,
        llm_model=result.model,
    )
    db.add(content)
    if body.llm_source == "platform":
        consume_platform_quota(db, tenant_id)
    db.commit()
    db.refresh(content)
    return get_content_for_tenant(db, content.id, tenant_id)
