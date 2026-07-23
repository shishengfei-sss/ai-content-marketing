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
from app.services.prompt_builder import (
    FORMAT_LABELS,
    PLATFORM_LABELS,
    _format_instruction,
    resolve_video_duration_sec,
    validate_platform_format,
)
from app.services.scope_service import can_view_content

_REVISE_SYSTEM = """你是营销内容编辑助手。根据用户修改指令改写原文，输出完整修改后正文。

规则：
1. 严格落实用户每一条修改意见（改标题、删除指定词、语气、篇幅、配图、换平台/形态等）
2. 保持营销合规，不编造数据与绝对化承诺；避免「有底气的保障」「百分百」「零风险」等表述
3. 若要求缩短：明显压缩篇幅，去掉重复表述
4. 若要求幽默：整体语气更轻松，仍专业可读
5. 若要求增加图片：在合适段落插入「【配图建议：…】」占位，不要编造外链 URL
6. 若要求改标题/去掉某词：全文（含标题）不得再出现被禁止的词
7. 若要求改成另一平台或形态（如公众号文章→小红书视频脚本）：按目标平台写法重写，保留核心观点与卖点，不要只改标题
8. 免责声明单独放在文末，不要与「联系我们」等行动号召写在同一段；禁止「郑重承诺绝不绝对化承诺」类自相矛盾句
9. 只输出修改后的完整正文，不要解释修改过程"""


async def revise_content_body(
    db: Session,
    ctx: TenantContext,
    content_id: UUID,
    instruction: str,
    *,
    llm_source: str = "platform",
    platform: str | None = None,
    content_format: str | None = None,
    video_duration_sec: int | None = None,
) -> Content:
    content = get_content_for_tenant(db, content_id, ctx.tenant_id)
    if not can_view_content(ctx, content.author_id):
        raise HTTPException(status_code=404, detail="内容不存在")
    if not instruction.strip():
        raise HTTPException(status_code=400, detail="改稿指令不能为空")

    target_platform = (platform or content.platform or "wechat").strip()
    target_format = (content_format or content.content_format or "article").strip()
    try:
        validate_platform_format(target_platform, target_format)
    except ValueError as e:
        if str(e) == "INVALID_PLATFORM_FORMAT":
            raise HTTPException(status_code=400, detail="该平台不支持所选内容形态") from e
        raise

    platform_changed = target_platform != (content.platform or "")
    format_changed = target_format != (content.content_format or "")
    adapt = platform_changed or format_changed

    platform_label = PLATFORM_LABELS.get(target_platform, target_platform)
    format_label = FORMAT_LABELS.get(target_format, target_format)
    format_rule = _format_instruction(
        target_platform,
        target_format,
        video_duration_sec=video_duration_sec,
    )

    user_parts = [
        f"当前标题/主题：{content.topic}",
        f"原文平台/形态：{PLATFORM_LABELS.get(content.platform or '', content.platform)} / "
        f"{FORMAT_LABELS.get(content.content_format or '', content.content_format)}",
        f"原文：\n{content.body}",
        f"修改指令：\n{instruction.strip()}",
    ]
    if adapt:
        user_parts.append(
            f"请将原文改写为【{platform_label}】的【{format_label}】。"
            f"保留核心观点、卖点与用户要求的称呼语气；按目标形态完整重写，不要只换标题。\n"
            f"{format_rule}"
        )
    user_parts.append("请输出修改后的完整正文。")

    messages = [
        LLMMessage(role="system", content=_REVISE_SYSTEM),
        LLMMessage(role="user", content="\n\n".join(user_parts)),
    ]
    result = await llm_service.chat(
        db,
        ctx.tenant_id,
        messages,
        llm_source=llm_source,
        check_platform_quota=False,
    )
    content.body = result.content
    content.platform = target_platform
    content.content_format = target_format
    content.llm_provider = result.provider
    content.llm_model = result.model
    db.commit()
    db.refresh(content)
    return content
