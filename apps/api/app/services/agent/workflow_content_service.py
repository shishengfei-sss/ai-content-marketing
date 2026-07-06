"""Agent 工作流专用内容步骤：深度分析 / 策略构思 / 自检优化。"""

from __future__ import annotations

import json
import logging
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Content, User
from app.schemas import ContentProposal
from app.services.assistant_service import require_active_assistant
from app.services.content_generation_service import raise_llm_config_error, validate_content_params
from app.services.content_service import get_content_for_tenant
from app.services.knowledge_service import get_template
from app.services.llm.base import LLMMessage
from app.services.llm_service import llm_service
from app.services.prompt_builder import default_content_format, parse_proposals_json

logger = logging.getLogger(__name__)

ANALYZE_SYSTEM = """你是营销内容策略分析师。先深度分析用户痛点与受众需求，不要撰写正文。
输出 JSON：
{
  "pain_points": ["痛点1", "痛点2"],
  "target_audience": "目标受众描述",
  "analysis_summary": "100字内分析摘要",
  "writing_guidance": "后续写作应聚焦的方向"
}
仅输出 JSON，无 markdown。"""

STRATEGY_SYSTEM = """你是营销选题策略师。基于痛点分析，列出 3 个备选标题方案，并说明为何推荐其中一个。
输出 JSON：
{
  "proposals": [
    {"title": "标题1", "angle": "切入角度", "outline": "内容大纲"},
    {"title": "标题2", "angle": "...", "outline": "..."},
    {"title": "标题3", "angle": "...", "outline": "..."}
  ],
  "selected_index": 0,
  "selection_rationale": "为何选择该标题的说明"
}
proposals 必须恰好 3 项，selected_index 为 0-2。仅输出 JSON，无 markdown。"""

OPTIMIZE_SYSTEM = """你是内容质检编辑。检查正文逻辑漏洞，精简冗余词汇，输出优化后的完整正文。
不要输出 JSON 或解释，直接输出优化后的正文。"""


def _strip_json_fence(text: str) -> str:
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
    return raw.strip()


def _parse_json_object(text: str, *, error_detail: str) -> dict:
    try:
        data = json.loads(_strip_json_fence(text))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=error_detail) from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail=error_detail)
    return data


async def run_analyze_pain_points(
    db: Session,
    tenant_id: UUID,
    *,
    platform: str,
    topic: str,
    scene: str,
    industry_code: str,
    llm_source: str,
    knowledge_results: list[dict] | None = None,
) -> dict:
    require_active_assistant(db, industry_code)
    template = get_template(db, industry_code, platform, scene)
    knowledge_block = ""
    if knowledge_results:
        snippets = [str(item.get("content") or "")[:300] for item in knowledge_results[:5]]
        knowledge_block = "\n".join(f"- {s}" for s in snippets if s)

    user_prompt = (
        f"平台：{platform}\n场景：{scene}\n"
        f"场景名：{template.name if template else ''}\n"
        f"主题：{topic}\n"
    )
    if knowledge_block:
        user_prompt += f"\n知识库参考：\n{knowledge_block}\n"
    user_prompt += "\n请分析目标用户痛点，不要写正文。"

    messages = [
        LLMMessage(role="system", content=ANALYZE_SYSTEM),
        LLMMessage(role="user", content=user_prompt),
    ]
    try:
        result = await llm_service.chat(
            db,
            tenant_id,
            messages,
            llm_source=llm_source,
            check_platform_quota=False,
        )
        data = _parse_json_object(result.content, error_detail="痛点分析失败，请重试")
    except ValueError as e:
        raise_llm_config_error(e)
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        logger.exception("analyze_pain_points LLM failed")
        raise HTTPException(status_code=502, detail="模型连接失败") from e

    pain_points = [str(p).strip() for p in (data.get("pain_points") or []) if str(p).strip()]
    return {
        "pain_points": pain_points,
        "target_audience": str(data.get("target_audience") or "").strip(),
        "analysis_summary": str(data.get("analysis_summary") or "").strip(),
        "writing_guidance": str(data.get("writing_guidance") or "").strip(),
    }


async def run_strategy_proposals(
    db: Session,
    tenant_id: UUID,
    *,
    platform: str,
    topic: str,
    scene: str,
    content_format: str,
    industry_code: str,
    llm_source: str,
    pain_analysis: dict | None = None,
) -> dict:
    content_format = validate_content_params(platform, content_format or default_content_format(platform))
    require_active_assistant(db, industry_code)
    template = get_template(db, industry_code, platform, scene)

    analysis_text = ""
    if pain_analysis:
        analysis_text = json.dumps(pain_analysis, ensure_ascii=False)

    user_prompt = (
        f"平台：{platform}\n场景：{scene}\n"
        f"场景名：{template.name if template else ''}\n"
        f"内容形态：{content_format}\n"
        f"主题：{topic}\n"
    )
    if analysis_text:
        user_prompt += f"\n痛点分析：\n{analysis_text}\n"
    user_prompt += "\n请给出 3 个备选标题，并说明推荐哪一个及原因。"

    messages = [
        LLMMessage(role="system", content=STRATEGY_SYSTEM),
        LLMMessage(role="user", content=user_prompt),
    ]
    try:
        result = await llm_service.chat(
            db,
            tenant_id,
            messages,
            llm_source=llm_source,
            check_platform_quota=False,
        )
        data = _parse_json_object(result.content, error_detail="策略构思失败，请重试")
        raw_items = data.get("proposals")
        if not isinstance(raw_items, list) or len(raw_items) < 1:
            raw_items = parse_proposals_json(result.content)
        proposals = [ContentProposal(**item).model_dump() for item in raw_items[:3]]
        while len(proposals) < 3:
            proposals.append(proposals[-1].copy())
        selected_index = int(data.get("selected_index", 0))
        selected_index = max(0, min(selected_index, len(proposals) - 1))
        rationale = str(data.get("selection_rationale") or "").strip()
    except ValueError as e:
        if str(e) == "PROPOSALS_PARSE_FAILED":
            raise HTTPException(status_code=502, detail="策略构思失败，请重试") from e
        raise_llm_config_error(e)
    except HTTPException:
        raise
    except httpx.HTTPError as e:
        logger.exception("strategy_proposals LLM failed")
        raise HTTPException(status_code=502, detail="模型连接失败") from e

    return {
        "proposals": proposals,
        "selected_index": selected_index,
        "selected_proposal": proposals[selected_index],
        "selection_rationale": rationale,
    }


async def run_optimize_content(
    db: Session,
    tenant_id: UUID,
    user: User,
    *,
    content_id: UUID,
    llm_source: str,
    pain_analysis: dict | None = None,
) -> Content:
    content = get_content_for_tenant(db, content_id, tenant_id)
    if content.author_id != user.id:
        raise HTTPException(status_code=404, detail="内容不存在")
    if not (content.body or "").strip():
        raise HTTPException(status_code=400, detail="正文为空，无法优化")

    context = ""
    if pain_analysis:
        context = f"\n创作背景（痛点分析）：\n{json.dumps(pain_analysis, ensure_ascii=False)}\n"

    messages = [
        LLMMessage(role="system", content=OPTIMIZE_SYSTEM),
        LLMMessage(
            role="user",
            content=(
                f"标题：{content.topic}\n"
                f"平台：{content.platform}\n"
                f"{context}\n"
                f"正文：\n{content.body}\n\n"
                "请自检逻辑漏洞并精简冗余，输出优化后的完整正文。"
            ),
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
    except httpx.HTTPError as e:
        logger.exception("optimize_content LLM failed")
        raise HTTPException(status_code=502, detail="模型连接失败") from e

    content.body = result.content
    content.llm_provider = result.provider
    content.llm_model = result.model
    db.commit()
    db.refresh(content)
    return content
