"""Agent Tool Registry：工具 schema + 统一执行入口。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models import Content, TenantMembership, User
from app.schemas import ContentGenerateRequest, ContentProposal, ContentProposalsRequest
from app.services.content_generation_service import run_generate_content, run_generate_proposals
from app.services.agent.workflow_content_service import (
    run_analyze_pain_points,
    run_optimize_content,
    run_strategy_proposals,
)
from app.services.agent.compliance_service import run_compliance_check, report_to_dict
from app.services.agent.seo_service import optimize_metadata
from app.services.agent.ops_service import (
    cancel_pending_action,
    confirm_pending_action,
    create_pending_publish,
    create_pending_schedule,
    list_pending_actions,
    pending_action_to_dict,
)
from app.services.content_service import get_content_for_tenant
from app.services.knowledge_service import list_templates, search_knowledge_scored
from app.services.platform_llm_service import get_quota_status
from app.services.publish_service import get_wechat_account
from app.services.scope_service import can_view_content


@dataclass(frozen=True)
class AgentToolContext:
    db: Session
    tenant_id: UUID
    user: User
    membership: TenantMembership
    permissions: frozenset[str]
    industry_code: str = "finance"

    def as_tenant_context(self) -> TenantContext:
        return TenantContext(user=self.user, tenant_id=self.tenant_id, membership=self.membership)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    required_permissions: frozenset[str]
    handler: Callable[[AgentToolContext, dict[str, Any]], Awaitable[dict[str, Any]]]


def _perm_ctx(ctx: TenantContext, db: Session, industry_code: str) -> AgentToolContext:
    perms = frozenset(p.permission_code for p in ctx.membership.role.permissions)
    return AgentToolContext(
        db=db,
        tenant_id=ctx.tenant_id,
        user=ctx.user,
        membership=ctx.membership,
        permissions=perms,
        industry_code=industry_code,
    )


async def _list_scenes(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    platform = args.get("platform")
    industry = args.get("industry_code") or ctx.industry_code
    items = list_templates(ctx.db, industry, platform)
    return {
        "scenes": [
            {
                "platform": t.platform,
                "scene": t.scene,
                "name": t.name,
                "prompt_hint": t.prompt_hint or "",
            }
            for t in items
        ]
    }


async def _search_knowledge(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="query 至少 2 个字符")
    industry = args.get("industry_code") or ctx.industry_code
    limit = min(int(args.get("limit") or 5), 10)
    mode = str(args.get("mode") or "hybrid")
    if mode not in ("keyword", "hybrid", "vector"):
        mode = "hybrid"
    hits = search_knowledge_scored(
        ctx.db,
        tenant_id=ctx.tenant_id,
        industry_code=industry,
        query=query,
        limit=limit,
        mode=mode,
    )
    return {
        "mode": mode,
        "results": [
            {
                "content": h.chunk.content[:500],
                "scope": h.chunk.scope,
                "tenant_id": str(h.chunk.tenant_id) if h.chunk.tenant_id else None,
                "industry_code": h.chunk.industry_code,
                "score": round(h.score, 4),
                "vector_score": round(h.vector_score, 4),
            }
            for h in hits
        ],
    }


async def _generate_proposals(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    body = ContentProposalsRequest(
        industry_code=args.get("industry_code") or ctx.industry_code,
        platform=args["platform"],
        scene=args.get("scene") or "",
        topic=args["topic"],
        content_format=args.get("content_format") or "article",
        llm_source=args.get("llm_source") or "platform",
    )
    result = await run_generate_proposals(ctx.db, ctx.tenant_id, body)
    return {"proposals": [p.model_dump() for p in result.proposals]}


async def _generate_content(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    proposal = None
    if args.get("selected_proposal"):
        proposal = ContentProposal(**args["selected_proposal"])
    body = ContentGenerateRequest(
        industry_code=args.get("industry_code") or ctx.industry_code,
        platform=args["platform"],
        scene=args.get("scene") or "",
        topic=args["topic"],
        content_format=args.get("content_format") or "article",
        llm_source=args.get("llm_source") or "platform",
        selected_proposal=proposal,
        ephemeral_instruction=str(args.get("ephemeral_instruction") or ""),
    )
    content = await run_generate_content(ctx.db, ctx.tenant_id, ctx.user, body)
    return {
        "content_id": str(content.id),
        "topic": content.topic,
        "platform": content.platform,
        "status": content.status,
        "body_preview": (content.body or "")[:200],
    }


async def _analyze_pain_points(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return await run_analyze_pain_points(
        ctx.db,
        ctx.tenant_id,
        platform=args["platform"],
        topic=args["topic"],
        scene=args.get("scene") or "",
        industry_code=args.get("industry_code") or ctx.industry_code,
        llm_source=args.get("llm_source") or "platform",
        knowledge_results=args.get("knowledge_results"),
    )


async def _strategy_proposals(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return await run_strategy_proposals(
        ctx.db,
        ctx.tenant_id,
        platform=args["platform"],
        topic=args["topic"],
        scene=args.get("scene") or "",
        content_format=args.get("content_format") or "article",
        industry_code=args.get("industry_code") or ctx.industry_code,
        llm_source=args.get("llm_source") or "platform",
        pain_analysis=args.get("pain_analysis"),
    )


async def _optimize_content(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    content = await run_optimize_content(
        ctx.db,
        ctx.tenant_id,
        ctx.user,
        content_id=UUID(str(args["content_id"])),
        llm_source=str(args.get("llm_source") or "platform"),
        pain_analysis=args.get("pain_analysis"),
    )
    return {
        "content_id": str(content.id),
        "topic": content.topic,
        "body_preview": (content.body or "")[:200],
        "status": content.status,
    }


async def _check_compliance(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    workflow_id = UUID(str(args["workflow_id"])) if args.get("workflow_id") else None
    report = await run_compliance_check(
        ctx.db,
        ctx.as_tenant_context(),
        content_id=UUID(str(args["content_id"])),
        workflow_id=workflow_id,
        llm_source=str(args.get("llm_source") or "platform"),
    )
    return report_to_dict(report)


async def _optimize_metadata(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return await optimize_metadata(
        ctx.db,
        ctx.as_tenant_context(),
        content_id=UUID(str(args["content_id"])),
        llm_source=str(args.get("llm_source") or "platform"),
    )


async def _review_for_publish(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from app.models import AgentComplianceReport

    content_id = UUID(str(args["content_id"]))
    content = get_content_for_tenant(ctx.db, content_id, ctx.tenant_id)
    if not can_view_content(ctx.as_tenant_context(), content.author_id):
        raise HTTPException(status_code=404, detail="内容不存在")
    report = (
        ctx.db.query(AgentComplianceReport)
        .filter(AgentComplianceReport.content_id == content_id)
        .order_by(AgentComplianceReport.created_at.desc())
        .first()
    )
    compliance_status = report.status if report else "unknown"
    return {
        "agent_code": "ops",
        "content_id": str(content_id),
        "compliance_status": compliance_status,
        "ready_for_publish": compliance_status in ("pass", "warn"),
        "publish_requires_confirm": True,
        "message": "Ops 就绪检查完成，发布须用户 confirm",
    }


async def _get_content(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    content_id = UUID(str(args["content_id"]))
    content = get_content_for_tenant(ctx.db, content_id, ctx.tenant_id)
    if not can_view_content(ctx.as_tenant_context(), content.author_id):
        raise HTTPException(status_code=404, detail="内容不存在")
    return {
        "id": str(content.id),
        "topic": content.topic,
        "platform": content.platform,
        "scene": content.scene,
        "status": content.status,
        "body": content.body,
        "content_format": content.content_format,
    }


async def _revise_content(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.content_revise_service import revise_content_body

    content_id = UUID(str(args["content_id"]))
    instruction = str(args.get("instruction") or "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction 不能为空")
    content = await revise_content_body(
        ctx.db,
        ctx.as_tenant_context(),
        content_id,
        instruction,
        llm_source=str(args.get("llm_source") or "platform"),
    )
    return {
        "content_id": str(content.id),
        "topic": content.topic,
        "body_preview": (content.body or "")[:200],
        "status": content.status,
    }


async def _get_quota(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _ = args
    return get_quota_status(ctx.db, ctx.tenant_id)


async def _get_wechat_settings(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _ = args
    account = get_wechat_account(ctx.db, ctx.tenant_id)
    account_type = account.account_type if account else "service"
    return {
        "bound": account is not None,
        "account_name": account.account_name if account else "",
        "account_type": account_type,
        "can_auto_publish": account is not None and account_type == "service",
    }


async def _publish_content(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    content_id = UUID(str(args["content_id"]))
    session_id = UUID(str(args["session_id"])) if args.get("session_id") else None
    pending = create_pending_publish(
        ctx.db,
        ctx.as_tenant_context(),
        content_id=content_id,
        session_id=session_id,
    )
    data = pending_action_to_dict(pending)
    return {
        "status": "pending_confirm",
        "action_id": data["action_id"],
        "action_type": "publish",
        "content_id": data["content_id"],
        "summary": data["summary"],
        "message": "发布须用户确认，请调用确认接口后执行",
    }


async def _schedule_content(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    content_id = UUID(str(args["content_id"]))
    scheduled_at = datetime.fromisoformat(str(args["scheduled_at"]).replace("Z", "+00:00"))
    session_id = UUID(str(args["session_id"])) if args.get("session_id") else None
    pending = create_pending_schedule(
        ctx.db,
        ctx.as_tenant_context(),
        content_id=content_id,
        scheduled_at=scheduled_at,
        session_id=session_id,
    )
    data = pending_action_to_dict(pending)
    return {
        "status": "pending_confirm",
        "action_id": data["action_id"],
        "action_type": "schedule",
        "content_id": data["content_id"],
        "summary": data["summary"],
        "scheduled_at": data["payload"].get("scheduled_at"),
        "message": "排期须用户确认，请调用确认接口后执行",
    }


async def _get_calendar(ctx: AgentToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _ = args
    items = (
        ctx.db.query(Content)
        .filter(
            Content.tenant_id == ctx.tenant_id,
            Content.status.in_(["scheduled", "published"]),
            Content.scheduled_at.isnot(None),
        )
        .order_by(Content.scheduled_at.asc())
        .limit(20)
        .all()
    )
    return {
        "events": [
            {
                "id": str(item.id),
                "title": item.topic,
                "platform": item.platform,
                "scheduled_at": item.scheduled_at.isoformat() if item.scheduled_at else None,
                "status": item.status,
            }
            for item in items
        ]
    }


TOOL_REGISTRY: dict[str, ToolSpec] = {}


def _register(
    name: str,
    description: str,
    parameters: dict[str, Any],
    required_permissions: frozenset[str],
    handler: Callable[[AgentToolContext, dict[str, Any]], Awaitable[dict[str, Any]]],
) -> None:
    TOOL_REGISTRY[name] = ToolSpec(
        name=name,
        description=description,
        parameters=parameters,
        required_permissions=required_permissions,
        handler=handler,
    )


_register(
    "list_scenes",
    "列出行业场景模板（平台+场景+名称）",
    {
        "type": "object",
        "properties": {
            "platform": {"type": "string", "enum": ["wechat", "xhs", "douyin"]},
            "industry_code": {"type": "string"},
        },
    },
    frozenset({"content.create"}),
    _list_scenes,
)

_register(
    "search_knowledge",
    "检索知识库（租户私有优先，再平台行业库）",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "industry_code": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["query"],
    },
    frozenset({"content.create", "knowledge.view"}),
    _search_knowledge,
)

_register(
    "generate_proposals",
    "生成选题方案（不扣平台额度）",
    {
        "type": "object",
        "properties": {
            "platform": {"type": "string", "enum": ["wechat", "xhs", "douyin"]},
            "scene": {"type": "string"},
            "topic": {"type": "string"},
            "content_format": {"type": "string", "enum": ["article", "note", "video_script"]},
            "industry_code": {"type": "string"},
            "llm_source": {"type": "string", "enum": ["platform", "tenant"]},
        },
        "required": ["platform", "topic"],
    },
    frozenset({"content.create"}),
    _generate_proposals,
)

_register(
    "analyze_pain_points",
    "深度分析用户痛点（工作流步骤，不扣额度）",
    {
        "type": "object",
        "properties": {
            "platform": {"type": "string", "enum": ["wechat", "xhs", "douyin"]},
            "scene": {"type": "string"},
            "topic": {"type": "string"},
            "industry_code": {"type": "string"},
            "llm_source": {"type": "string", "enum": ["platform", "tenant"]},
            "knowledge_results": {"type": "array"},
        },
        "required": ["platform", "topic"],
    },
    frozenset({"content.create"}),
    _analyze_pain_points,
)

_register(
    "strategy_proposals",
    "策略构思：3 个备选标题并说明推荐理由（不扣额度）",
    {
        "type": "object",
        "properties": {
            "platform": {"type": "string", "enum": ["wechat", "xhs", "douyin"]},
            "scene": {"type": "string"},
            "topic": {"type": "string"},
            "content_format": {"type": "string", "enum": ["article", "note", "video_script"]},
            "industry_code": {"type": "string"},
            "llm_source": {"type": "string", "enum": ["platform", "tenant"]},
            "pain_analysis": {"type": "object"},
        },
        "required": ["platform", "topic"],
    },
    frozenset({"content.create"}),
    _strategy_proposals,
)

_register(
    "generate_content",
    "生成正文并入库（平台额度扣 1 次）",
    {
        "type": "object",
        "properties": {
            "platform": {"type": "string", "enum": ["wechat", "xhs", "douyin"]},
            "scene": {"type": "string"},
            "topic": {"type": "string"},
            "content_format": {"type": "string", "enum": ["article", "note", "video_script"]},
            "selected_proposal": {"type": "object"},
            "ephemeral_instruction": {"type": "string"},
            "industry_code": {"type": "string"},
            "llm_source": {"type": "string", "enum": ["platform", "tenant"]},
        },
        "required": ["platform", "topic"],
    },
    frozenset({"content.create"}),
    _generate_content,
)

_register(
    "optimize_content",
    "自检优化：检查逻辑漏洞并精简冗余（不扣额度）",
    {
        "type": "object",
        "properties": {
            "content_id": {"type": "string", "format": "uuid"},
            "llm_source": {"type": "string", "enum": ["platform", "tenant"]},
            "pain_analysis": {"type": "object"},
        },
        "required": ["content_id"],
    },
    frozenset({"content.create"}),
    _optimize_content,
)

_register(
    "check_compliance",
    "合规审查：检查免责声明与违规承诺（不扣额度，不触发审核流）",
    {
        "type": "object",
        "properties": {
            "content_id": {"type": "string", "format": "uuid"},
            "workflow_id": {"type": "string", "format": "uuid"},
            "llm_source": {"type": "string", "enum": ["platform", "tenant"]},
        },
        "required": ["content_id"],
    },
    frozenset({"content.create"}),
    _check_compliance,
)

_register(
    "review_for_publish",
    "Ops 就绪检查：确认合规状态，不直接发布",
    {
        "type": "object",
        "properties": {
            "content_id": {"type": "string", "format": "uuid"},
        },
        "required": ["content_id"],
    },
    frozenset({"content.create"}),
    _review_for_publish,
)

_register(
    "optimize_metadata",
    "Seo 优化：生成标题候选与平台标签（不扣额度）",
    {
        "type": "object",
        "properties": {
            "content_id": {"type": "string", "format": "uuid"},
            "llm_source": {"type": "string", "enum": ["platform", "tenant"]},
        },
        "required": ["content_id"],
    },
    frozenset({"content.create"}),
    _optimize_metadata,
)

_register(
    "get_content",
    "读取内容详情（受数据范围约束）",
    {
        "type": "object",
        "properties": {"content_id": {"type": "string", "format": "uuid"}},
        "required": ["content_id"],
    },
    frozenset({"content.view_own", "content.view_all"}),
    _get_content,
)

_register(
    "revise_content",
    "按指令改稿（B3 实现，当前占位）",
    {
        "type": "object",
        "properties": {
            "content_id": {"type": "string", "format": "uuid"},
            "instruction": {"type": "string"},
        },
        "required": ["content_id", "instruction"],
    },
    frozenset({"content.edit"}),
    _revise_content,
)

_register(
    "get_quota",
    "查询平台 AI 额度状态",
    {"type": "object", "properties": {}},
    frozenset({"content.create"}),
    _get_quota,
)

_register(
    "get_wechat_settings",
    "查询公众号绑定与自动发布能力",
    {"type": "object", "properties": {}},
    frozenset({"wechat.manage", "content.create"}),
    _get_wechat_settings,
)

_register(
    "publish_content",
    "请求发布内容（创建待确认操作，须用户 confirm 后才真正发布）",
    {
        "type": "object",
        "properties": {
            "content_id": {"type": "string", "format": "uuid"},
            "session_id": {"type": "string", "format": "uuid"},
        },
        "required": ["content_id"],
    },
    frozenset({"content.publish"}),
    _publish_content,
)

_register(
    "schedule_content",
    "请求排期发布（创建待确认操作，须用户 confirm 后才生效）",
    {
        "type": "object",
        "properties": {
            "content_id": {"type": "string", "format": "uuid"},
            "scheduled_at": {"type": "string", "format": "date-time"},
            "session_id": {"type": "string", "format": "uuid"},
        },
        "required": ["content_id", "scheduled_at"],
    },
    frozenset({"content.schedule"}),
    _schedule_content,
)

_register(
    "get_calendar",
    "获取排期/已发布日历事件",
    {"type": "object", "properties": {}},
    frozenset({"content.create"}),
    _get_calendar,
)


def _has_tool_permission(ctx: AgentToolContext, tool: ToolSpec) -> bool:
    if not tool.required_permissions:
        return True
    return bool(ctx.permissions.intersection(tool.required_permissions))


def list_available_tools(ctx: AgentToolContext) -> list[dict[str, Any]]:
    tools = []
    for spec in TOOL_REGISTRY.values():
        if _has_tool_permission(ctx, spec):
            tools.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                    "required_permissions": sorted(spec.required_permissions),
                }
            )
    return sorted(tools, key=lambda t: t["name"])


def get_tool_spec(name: str) -> ToolSpec:
    spec = TOOL_REGISTRY.get(name)
    if not spec:
        raise HTTPException(status_code=404, detail=f"未知工具: {name}")
    return spec


async def execute_tool(
    ctx: AgentToolContext,
    name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = get_tool_spec(name)
    if not _has_tool_permission(ctx, spec):
        raise HTTPException(status_code=403, detail=f"无权使用工具 {name}")
    args = arguments or {}
    try:
        return await spec.handler(ctx, args)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"工具执行失败: {e}") from e
