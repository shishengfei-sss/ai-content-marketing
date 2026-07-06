"""Agent 意图解析：LLM 输出结构化 JSON。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.llm.base import LLMMessage
from app.services.llm_service import llm_service
from app.services.content_generation_service import raise_llm_config_error

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """你是营销创作意图解析器。根据用户消息输出唯一 JSON 对象，字段：
- action: proposals | generate | chat | clarify
- platform: wechat | xhs | douyin | null
- scene: string | null（默认 bookkeeping_intro）
- content_format: article | note | video_script | null
- topic: string
- clarify_question: string | null
- selected_proposal_index: number | null

规则：
1. 信息不足（无平台/主题）→ action=clarify，clarify_question 用中文追问
2. 用户要方案/选题 → action=proposals，补齐 platform/scene/topic
3. 用户明确要生成正文或选定方案 → action=generate
4. 仅闲聊 → action=chat
仅输出 JSON，无 markdown。"""


@dataclass
class ParsedIntent:
    action: str
    platform: str | None = None
    scene: str | None = None
    content_format: str | None = None
    topic: str = ""
    clarify_question: str | None = None
    selected_proposal_index: int | None = None


def _parse_intent_json(raw: str) -> ParsedIntent:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("intent JSON parse failed: %s", raw[:200])
        raise HTTPException(status_code=502, detail="意图解析失败，请重试") from e

    action = (data.get("action") or "chat").strip().lower()
    platform = data.get("platform")
    if platform in ("null", ""):
        platform = None
    scene = data.get("scene") or None
    content_format = data.get("content_format")
    if content_format in ("null", ""):
        content_format = None
    topic = (data.get("topic") or "").strip()
    clarify = data.get("clarify_question")
    idx = data.get("selected_proposal_index")
    if idx is not None:
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            idx = None
    return ParsedIntent(
        action=action,
        platform=platform,
        scene=scene or "bookkeeping_intro",
        content_format=content_format,
        topic=topic,
        clarify_question=clarify,
        selected_proposal_index=idx,
    )


async def parse_intent(
    db: Session,
    tenant_id: UUID,
    *,
    message: str,
    industry_code: str,
    llm_source: str = "platform",
    selected_proposal_index: int | None = None,
    force_action: str | None = None,
    memory_context: str = "",
) -> ParsedIntent:
    if force_action == "generate" and selected_proposal_index is not None:
        return ParsedIntent(
            action="generate",
            platform="wechat",
            scene="bookkeeping_intro",
            content_format="article",
            topic=message or "营销内容",
            selected_proposal_index=selected_proposal_index,
        )

    context = ""
    if selected_proposal_index is not None:
        context = f"\n上下文：用户已选择方案索引 {selected_proposal_index}，倾向 action=generate。"
    if memory_context.strip():
        context += f"\n\n{memory_context.strip()}"

    messages = [
        LLMMessage(role="system", content=INTENT_SYSTEM_PROMPT),
        LLMMessage(
            role="user",
            content=f"行业={industry_code}\n用户消息：{message}{context}",
        ),
    ]
    try:
        result = await llm_service.chat(
            db,
            tenant_id,
            messages,
            llm_source=llm_source,
            check_platform_quota=False,
        )
    except ValueError as e:
        raise_llm_config_error(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("intent parse LLM failed")
        raise HTTPException(status_code=502, detail=f"意图解析失败: {e}") from e

    intent = _parse_intent_json(result.content)
    if selected_proposal_index is not None and intent.action in ("proposals", "chat"):
        intent.action = "generate"
        intent.selected_proposal_index = selected_proposal_index
    return intent
