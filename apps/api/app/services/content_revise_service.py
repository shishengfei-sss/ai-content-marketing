"""内容改稿服务（Agent B3）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models import Content
from app.services.content_service import get_content_for_tenant
from app.services.llm.base import LLMMessage
from app.services.llm_service import llm_service
from app.services.scope_service import can_view_content


async def revise_content_body(
    db: Session,
    ctx: TenantContext,
    content_id: UUID,
    instruction: str,
    *,
    llm_source: str = "platform",
) -> Content:
    content = get_content_for_tenant(db, content_id, ctx.tenant_id)
    if not can_view_content(ctx, content.author_id):
        raise HTTPException(status_code=404, detail="内容不存在")
    if not instruction.strip():
        raise HTTPException(status_code=400, detail="改稿指令不能为空")

    messages = [
        LLMMessage(
            role="system",
            content="你是营销内容编辑助手。根据用户指令修改原文，保持合规，输出完整修改后正文。",
        ),
        LLMMessage(
            role="user",
            content=f"原文：\n{content.body}\n\n修改指令：{instruction.strip()}\n\n请输出修改后的完整正文。",
        ),
    ]
    result = await llm_service.chat(
        db,
        ctx.tenant_id,
        messages,
        llm_source=llm_source,
        check_platform_quota=False,
    )
    content.body = result.content
    content.llm_provider = result.provider
    content.llm_model = result.model
    db.commit()
    db.refresh(content)
    return content
