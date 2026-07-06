"""SeoAgent：标题候选与平台标签优化（C6，不扣额度）。"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.services.content_generation_service import raise_llm_config_error
from app.services.content_service import get_content_for_tenant
from app.services.llm.base import LLMMessage
from app.services.llm_service import llm_service
from app.services.scope_service import can_view_content

SEO_SYSTEM = """你是营销内容 SEO 优化助手。根据正文与平台输出 JSON：
{
  "title_candidates": ["标题1","标题2","标题3"],
  "tags": ["标签1","标签2","标签3"]
}
title_candidates 至少 3 条，tags 为平台适配关键词。仅输出 JSON，无 markdown。"""


def _parse_seo_json(raw: str) -> tuple[list[str], list[str]]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail="SEO 结果解析失败") from e
    titles = [str(t).strip() for t in (data.get("title_candidates") or []) if str(t).strip()]
    tags = [str(t).strip() for t in (data.get("tags") or []) if str(t).strip()]
    if len(titles) < 3:
        raise HTTPException(status_code=502, detail="SEO 标题候选不足 3 条")
    return titles[:5], tags[:10]


async def optimize_metadata(
    db: Session,
    ctx: TenantContext,
    *,
    content_id: UUID,
    llm_source: str = "platform",
) -> dict:
    content = get_content_for_tenant(db, content_id, ctx.tenant_id)
    if not can_view_content(ctx, content.author_id):
        raise HTTPException(status_code=404, detail="内容不存在")

    messages = [
        LLMMessage(role="system", content=SEO_SYSTEM),
        LLMMessage(
            role="user",
            content=(
                f"平台：{content.platform}\n"
                f"场景：{content.scene}\n"
                f"当前标题：{content.topic}\n"
                f"正文：\n{(content.body or '')[:2000]}"
            ),
        ),
    ]
    try:
        result = await llm_service.chat(
            db,
            ctx.tenant_id,
            messages,
            llm_source=llm_source,
            check_platform_quota=False,
        )
    except ValueError as e:
        raise_llm_config_error(e)

    titles, tags = _parse_seo_json(result.content)
    return {
        "content_id": str(content.id),
        "platform": content.platform,
        "title_candidates": titles,
        "tags": tags,
    }
