"""合规审查后的自动改稿循环（v1.1 P1 FR-CREATE-10）。

供 Agent 路径复用；Workflow 继续写步骤审计，但共用指令构建逻辑。
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models import Content
from app.services.agent.compliance_service import report_to_dict, run_compliance_check
from app.services.content_revise_service import revise_content_body
from app.services.content_service import get_content_for_tenant

logger = logging.getLogger(__name__)

MAX_COMPLIANCE_REVISE_ROUNDS = 3


def build_compliance_revise_instruction(
    *,
    issues: list | None = None,
    suggestions: list | None = None,
    ctx_data: dict | None = None,
) -> str:
    """从合规结果或 Workflow ctx_data 构建改稿指令。"""
    if ctx_data is not None:
        issues = ctx_data.get("_compliance_issues") or issues or []
        suggestions = ctx_data.get("_compliance_suggestions") or suggestions or []
    issues = issues or []
    suggestions = suggestions or []
    parts: list[str] = []
    for item in issues:
        if not isinstance(item, dict):
            continue
        msg = str(item.get("message") or "").strip()
        if not msg:
            continue
        severity = str(item.get("severity") or "").strip().lower()
        if severity == "block":
            parts.append(f"必须删除或改写违规内容：{msg}")
        else:
            parts.append(f"建议修正：{msg}")
    for s in suggestions:
        text = str(s).strip()
        if text and text not in parts:
            parts.append(text)
    parts.append("文末须保留行业免责声明，不得出现绝对化承诺、稳赚不赔、100%成功等用语。")
    return "；".join(parts) if parts else "请修正合规问题并保留免责声明。"


async def revise_until_pass(
    db: Session,
    ctx: TenantContext,
    content_id: UUID,
    *,
    llm_source: str = "platform",
    max_rounds: int = MAX_COMPLIANCE_REVISE_ROUNDS,
    use_llm_check: bool = True,
) -> tuple[Content, dict]:
    """合规 block 时改稿并重检，最多 max_rounds 次。

    返回 (content, info)，info 含 rounds / final_status / still_blocked。
    """
    report = await run_compliance_check(
        db,
        ctx,
        content_id=content_id,
        llm_source=llm_source,
        use_llm=use_llm_check,
    )
    status = str(report.status or "")
    rounds = 0
    result = report_to_dict(report)

    while status == "block" and rounds < max_rounds:
        instruction = build_compliance_revise_instruction(
            issues=result.get("issues") or [],
            suggestions=result.get("suggestions") or [],
        )
        await revise_content_body(
            db,
            ctx,
            content_id,
            instruction,
            llm_source=llm_source,
        )
        report = await run_compliance_check(
            db,
            ctx,
            content_id=content_id,
            llm_source=llm_source,
            use_llm=use_llm_check,
        )
        result = report_to_dict(report)
        status = str(report.status or "")
        rounds += 1

    content = get_content_for_tenant(db, content_id, ctx.tenant_id)
    still_blocked = status == "block"
    if not still_blocked and rounds > 0:
        content.status = "draft"
        if content.publish_error and str(content.publish_error).startswith("[COMPLIANCE_"):
            content.publish_error = None
        db.commit()
        db.refresh(content)
    elif still_blocked:
        content.status = "compliance_blocked"
        content.publish_error = content.publish_error or "[COMPLIANCE_BLOCK]"
        db.commit()
        db.refresh(content)

    info = {
        "rounds": rounds,
        "final_status": status,
        "still_blocked": still_blocked,
    }
    logger.info(
        "compliance revise loop content_id=%s rounds=%s status=%s blocked=%s",
        content_id,
        rounds,
        status,
        still_blocked,
    )
    return content, info
