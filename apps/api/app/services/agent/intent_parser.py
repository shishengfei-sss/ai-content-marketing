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
from app.services.assistant_service import normalize_advisor_code
from app.services.proposal_count import resolve_proposal_count

logger = logging.getLogger(__name__)

PREFLIGHT_SYSTEM_PROMPT = """你是通用营销创作预检解析器。根据用户描述输出唯一 JSON 对象，字段：
- action: proceed | clarify
- topic: string
- clarify_question: string | null
- proposal_count: number | null（用户明确要求的方向/标题/方案个数，1～10；未指定则为 null）
- input_class: greeting | joke | off_topic | too_short | vague | proceed（输入分类，便于日志）

规则：
1. 上下文已给出 UI 选择的 platform 与 content_format，禁止追问平台或形态
2. 若对话历史中有此前 clarify 与用户补充，须合并理解，禁止重复追问已回答内容
3. 只要用户表达了明确创作主题（某产品/某话题/某人物/某事件等）→ action=proceed，即使缺少受众或要点也放行，由后续方案生成环节细化；topic 提炼为一句简洁创作主题
4. 仅以下情况才 clarify：纯寒暄（你好/在吗）、只有动词无主题（"写一篇"/"帮我写"）、完全跑题（股票行情等）、或有效汉字不足 4 个
5. clarify 时 clarify_question 用中文一次追问 1 点，并给出下一步建议；禁止与历史 clarify 问题重复
6. 用户说「10个方向/标题」等 → proposal_count 填对应数字（最大 10）；未指定数量 → proposal_count=null
7. 玩笑、偏题或与创作无关 → action=clarify，礼貌拉回营销创作主线
仅输出 JSON，无 markdown。"""


INTENT_SYSTEM_PROMPT = """你是营销创作意图解析器。根据用户消息输出唯一 JSON 对象，字段：
- action: proposals | generate | chat | clarify
- platform: wechat | xhs | douyin | null
- scene: string | null（默认 brand_intro）
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
    proposal_count: int | None = None
    input_class: str | None = None


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
        scene=scene or "brand_intro",
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
            scene="brand_intro",
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


def _parse_preflight_json(raw: str) -> ParsedIntent:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("preflight JSON parse failed: %s", raw[:200])
        raise HTTPException(status_code=502, detail="预检解析失败，请重试") from e

    action = (data.get("action") or "clarify").strip().lower()
    if action not in ("proceed", "clarify"):
        action = "clarify"
    topic = (data.get("topic") or "").strip()
    clarify = data.get("clarify_question")
    raw_count = data.get("proposal_count")
    proposal_count: int | None = None
    if raw_count is not None and raw_count != "":
        try:
            proposal_count = resolve_proposal_count(explicit=int(raw_count), text=topic)
        except (TypeError, ValueError):
            proposal_count = None
    return ParsedIntent(
        action=action,
        topic=topic,
        clarify_question=clarify,
        proposal_count=proposal_count,
        input_class=(data.get("input_class") or None),
    )


async def parse_create_preflight(
    db: Session,
    tenant_id: UUID,
    *,
    message: str,
    platform: str,
    content_format: str,
    industry_code: str,
    llm_source: str = "platform",
    conversation_context: str | None = None,
) -> ParsedIntent:
    platform_labels = {"wechat": "公众号", "xhs": "小红书", "douyin": "抖音"}
    format_labels = {"article": "图文", "note": "笔记", "video_script": "视频脚本"}
    user_text = (conversation_context or message).strip()
    user_content = (
        f"顾问=通用营销创作（{normalize_advisor_code(industry_code)}）\n"
        f"UI已选平台={platform}（{platform_labels.get(platform, platform)}）\n"
        f"UI已选形态={content_format}（{format_labels.get(content_format, content_format)}）\n"
        f"用户描述与对话：\n{user_text}"
    )
    messages = [
        LLMMessage(role="system", content=PREFLIGHT_SYSTEM_PROMPT),
        LLMMessage(role="user", content=user_content),
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
        logger.exception("preflight LLM failed")
        err = str(e)
        if "401" in err or "Authorization Required" in err:
            raise HTTPException(
                status_code=502,
                detail="预检失败：平台 DeepSeek API Key 无效或未配置，请在管理后台「平台 AI」或 apps/api/.env 中设置 DEEPSEEK_API_KEY",
            ) from e
        raise HTTPException(status_code=502, detail=f"预检失败: {e}") from e

    intent = _parse_preflight_json(result.content)
    merged_count = resolve_proposal_count(explicit=intent.proposal_count, text=user_text)
    intent.proposal_count = merged_count
    return intent
