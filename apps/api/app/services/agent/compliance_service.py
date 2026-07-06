"""ComplianceAgent：合规审查（C2）。仅建议/拦截，不触发审核流。"""

from __future__ import annotations

import json
import logging
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import AgentComplianceReport, Content
from app.services.assistant_service import get_profile
from app.services.content_generation_service import raise_llm_config_error
from app.services.content_service import get_content_for_tenant
from app.services.llm.base import LLMMessage
from app.services.llm_service import llm_service
from app.services.scope_service import can_view_content

logger = logging.getLogger(__name__)

DISCLAIMER_MARKERS = (
    "仅供参考",
    "以税务机关最新规定为准",
    "以相关部门最新规定为准",
)
BLOCK_TERMS = ("绝对保证", "100%成功", "稳赚不赔", "包过审核")

COMPLIANCE_SYSTEM = """你是营销内容合规审查员。检查正文是否含夸大承诺、缺失免责声明等问题。
输出 JSON：
{
  "status": "pass|warn|block",
  "issues": [{"code": "ISSUE_CODE", "severity": "warn|block", "message": "说明"}],
  "suggestions": ["修改建议1"]
}
block 仅用于明显违规承诺；缺少免责声明通常为 warn。仅输出 JSON，无 markdown。"""


def _dump_list(items: list) -> str:
    return json.dumps(items, ensure_ascii=False)


def _load_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _rule_check(body: str, *, disclaimer: str) -> list[dict]:
    text = body or ""
    issues: list[dict] = []
    has_disclaimer = any(marker in text for marker in DISCLAIMER_MARKERS) or (
        disclaimer and disclaimer in text
    )
    if not has_disclaimer:
        issues.append(
            {
                "code": "MISSING_DISCLAIMER",
                "severity": "warn",
                "message": "正文缺少合规免责声明",
            }
        )
    for term in BLOCK_TERMS:
        if term in text:
            issues.append(
                {
                    "code": "FORBIDDEN_CLAIM",
                    "severity": "block",
                    "message": f"含违规承诺用语：{term}",
                }
            )
    return issues


def _resolve_status(issues: list[dict]) -> str:
    if any(item.get("severity") == "block" for item in issues):
        return "block"
    if issues:
        return "warn"
    return "pass"


def _merge_llm_issues(rule_issues: list[dict], llm_issues: list[dict]) -> list[dict]:
    merged = list(rule_issues)
    seen = {(i.get("code"), i.get("message")) for i in merged}
    for item in llm_issues:
        key = (item.get("code"), item.get("message"))
        if key not in seen:
            merged.append(item)
            seen.add(key)
    return merged


async def run_compliance_check(
    db: Session,
    ctx: TenantContext,
    *,
    content_id: UUID,
    workflow_id: UUID | None = None,
    llm_source: str = "platform",
    use_llm: bool = True,
) -> AgentComplianceReport:
    content = get_content_for_tenant(db, content_id, ctx.tenant_id)
    if not can_view_content(ctx, content.author_id):
        raise HTTPException(status_code=404, detail="内容不存在")

    assistant = get_profile(db, content.industry_code)
    rule_issues = _rule_check(content.body or "", disclaimer=assistant.disclaimer)
    suggestions: list[str] = []
    status = _resolve_status(rule_issues)

    if use_llm:
        messages = [
            LLMMessage(role="system", content=COMPLIANCE_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f"标题：{content.topic}\n"
                    f"平台：{content.platform}\n"
                    f"行业免责声明：{assistant.disclaimer}\n"
                    f"正文：\n{content.body or ''}"
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
            raw = result.content.strip()
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
            data = json.loads(raw)
            llm_issues = data.get("issues") if isinstance(data.get("issues"), list) else []
            llm_suggestions = data.get("suggestions") if isinstance(data.get("suggestions"), list) else []
            rule_issues = _merge_llm_issues(rule_issues, llm_issues)
            suggestions = [str(s) for s in llm_suggestions if str(s).strip()]
            llm_status = str(data.get("status") or "").strip().lower()
            status = _resolve_status(rule_issues)
            if llm_status in ("pass", "warn", "block") and status != "block":
                status = llm_status if llm_status != "pass" or not rule_issues else "pass"
        except ValueError as e:
            raise_llm_config_error(e)
        except (json.JSONDecodeError, httpx.HTTPError, Exception) as e:
            logger.warning("LLM compliance fallback to rules: %s", e)

    if status == "warn" and not suggestions:
        suggestions = ["建议在文末补充行业免责声明，并避免绝对化承诺。"]
    if status == "block" and not suggestions:
        suggestions = ["请删除夸大承诺用语后再发布。"]

    report = AgentComplianceReport(
        content_id=content.id,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        workflow_id=workflow_id,
        status=status,
        issues_json=_dump_list(rule_issues),
        suggestions_json=_dump_list(suggestions),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_compliance_report(db: Session, report_id: UUID, ctx: TenantContext) -> AgentComplianceReport:
    report = (
        db.query(AgentComplianceReport)
        .filter(
            uuid_eq(AgentComplianceReport.id, report_id),
            uuid_eq(AgentComplianceReport.tenant_id, ctx.tenant_id),
            uuid_eq(AgentComplianceReport.user_id, ctx.user.id),
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="合规报告不存在")
    return report


def report_to_dict(report: AgentComplianceReport) -> dict:
    return {
        "report_id": str(report.id),
        "content_id": str(report.content_id),
        "status": report.status,
        "issues": _load_list(report.issues_json),
        "suggestions": _load_list(report.suggestions_json),
        "workflow_id": str(report.workflow_id) if report.workflow_id else None,
    }
