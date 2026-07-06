from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AgentMemoryContextOut,
    AgentMemoryCreate,
    AgentMemoryOut,
    AgentMemoryUpdate,
    AgentRecallResponse,
    AgentSessionSummaryOut,
    AgentMessageCreate,
    AgentMessageOut,
    AgentSessionCreate,
    AgentSessionOut,
    AgentToolExecuteRequest,
    AgentToolOut,
    AgentComplianceCheckRequest,
    AgentComplianceReportOut,
    AgentOpsConfirmOut,
    AgentPendingActionOut,
    AgentSeoOptimizeRequest,
    AgentSeoOptimizeOut,
    AgentWorkflowCreate,
    AgentWorkflowOut,
    AgentWorkflowStepOut,
)
from app.services.agent.chat_service import handle_chat
from app.services.agent.chat_stream_service import stream_chat
from app.services.agent.memory_service import (
    create_memory,
    delete_memory,
    get_memory,
    list_memories,
    update_memory,
)
from app.services.agent.memory_injection import (
    DEFAULT_MAX_CHARS,
    build_memory_context,
    format_memory_block,
    truncate_text,
)
from app.services.agent.pipelines import list_pipelines
from app.services.agent.summary_service import generate_session_summary, get_session_summary, recall_memories
from app.services.agent.workflow_manager import (
    create_workflow,
    get_workflow,
    get_workflow_handoffs,
    list_workflows,
    run_workflow,
)
from app.services.agent.supervisor_service import list_agents
from app.services.agent.compliance_service import get_compliance_report, run_compliance_check
from app.services.agent.seo_service import optimize_metadata
from app.services.agent.ops_service import (
    cancel_pending_action,
    confirm_pending_action,
    list_pending_actions,
    pending_action_to_dict,
)
from app.services.agent.orchestrator import handle_react_chat
from app.services.agent.session_service import (
    append_message,
    create_session,
    get_session,
    list_messages,
    list_sessions,
)
from app.services.agent.tools import _perm_ctx, execute_tool, list_available_tools
from app.services.permission_service import require_permission

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/health")
def agent_health():
    return {"status": "ok", "module": "agent"}


@router.post("/sessions", response_model=AgentSessionOut)
def post_session(
    body: AgentSessionCreate,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    return create_session(
        db,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        industry_code=body.industry_code,
        title=body.title,
    )


@router.get("/sessions", response_model=list[AgentSessionOut])
def get_sessions(
    limit: int = 20,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 50))
    return list_sessions(db, tenant_id=ctx.tenant_id, user_id=ctx.user.id, limit=limit)


@router.get("/sessions/{session_id}", response_model=AgentSessionOut)
def get_session_detail(
    session_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    return get_session(db, session_id, tenant_id=ctx.tenant_id, user_id=ctx.user.id)


@router.get("/sessions/{session_id}/messages", response_model=list[AgentMessageOut])
def get_session_messages(
    session_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    get_session(db, session_id, tenant_id=ctx.tenant_id, user_id=ctx.user.id)
    return list_messages(db, session_id)


@router.post("/sessions/{session_id}/messages", response_model=AgentMessageOut)
def post_session_message(
    session_id: UUID,
    body: AgentMessageCreate,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    session = get_session(db, session_id, tenant_id=ctx.tenant_id, user_id=ctx.user.id)
    return append_message(
        db,
        session,
        role=body.role,
        content=body.content,
        message_type=body.message_type,
        metadata=body.metadata,
    )


@router.post("/sessions/{session_id}/chat", response_model=AgentChatResponse)
async def post_session_chat(
    session_id: UUID,
    body: AgentChatRequest,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    session = get_session(db, session_id, tenant_id=ctx.tenant_id, user_id=ctx.user.id)
    if body.mode == "react":
        return await handle_react_chat(
            db,
            session,
            ctx.user,
            ctx,
            message=body.message,
            llm_source=body.llm_source,
        )
    return await handle_chat(
        db,
        session,
        ctx.user,
        message=body.message,
        llm_source=body.llm_source,
        selected_proposal_index=body.selected_proposal_index,
        tenant_ctx=ctx,
    )


@router.post("/sessions/{session_id}/chat/stream")
async def post_session_chat_stream(
    session_id: UUID,
    body: AgentChatRequest,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    if body.mode == "react":
        raise HTTPException(status_code=400, detail="ReAct 模式请使用非流式 chat 接口")
    session = get_session(db, session_id, tenant_id=ctx.tenant_id, user_id=ctx.user.id)

    async def event_generator():
        async for chunk in stream_chat(
            db,
            session,
            ctx.user,
            message=body.message,
            llm_source=body.llm_source,
            selected_proposal_index=body.selected_proposal_index,
        ):
            yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/tools", response_model=list[AgentToolOut])
def get_agent_tools(
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    tool_ctx = _perm_ctx(ctx, db, industry_code="finance")
    return list_available_tools(tool_ctx)


@router.post("/tools/execute")
async def post_agent_tool_execute(
    body: AgentToolExecuteRequest,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    tool_ctx = _perm_ctx(ctx, db, industry_code=body.industry_code)
    return await execute_tool(tool_ctx, body.name, body.arguments)


@router.get("/memories", response_model=list[AgentMemoryOut])
def get_agent_memories(
    scope: str | None = None,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    return list_memories(db, ctx, scope=scope)


@router.post("/memories", response_model=AgentMemoryOut)
def post_agent_memory(
    body: AgentMemoryCreate,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    return create_memory(
        db,
        ctx,
        scope=body.scope,
        fact_text=body.fact_text,
        category=body.category,
        source=body.source,
        is_confirmed=body.is_confirmed,
    )


@router.get("/memories/{memory_id}", response_model=AgentMemoryOut)
def get_agent_memory(
    memory_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    return get_memory(db, memory_id, ctx)


@router.patch("/memories/{memory_id}", response_model=AgentMemoryOut)
def patch_agent_memory(
    memory_id: UUID,
    body: AgentMemoryUpdate,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    return update_memory(
        db,
        memory_id,
        ctx,
        fact_text=body.fact_text,
        category=body.category,
        is_confirmed=body.is_confirmed,
    )


@router.post("/memories/{memory_id}/confirm", response_model=AgentMemoryOut)
def post_agent_memory_confirm(
    memory_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    from app.services.agent.memory_service import confirm_memory

    return confirm_memory(db, memory_id, ctx)


@router.delete("/memories/{memory_id}")
def delete_agent_memory(
    memory_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    delete_memory(db, memory_id, ctx)
    return {"message": "已删除"}


@router.post("/sessions/{session_id}/summary", response_model=AgentSessionSummaryOut)
async def post_session_summary(
    session_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
    llm_source: str = "platform",
):
    return await generate_session_summary(db, ctx, session_id, llm_source=llm_source)


@router.get("/sessions/{session_id}/summary", response_model=AgentSessionSummaryOut)
def get_session_summary_detail(
    session_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    return get_session_summary(db, ctx, session_id)


@router.get("/recall", response_model=AgentRecallResponse)
def get_agent_recall(
    q: str,
    limit: int = 10,
    mode: str = "keyword",
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    if mode not in ("keyword", "hybrid"):
        raise HTTPException(status_code=400, detail="mode 必须为 keyword 或 hybrid")
    data = recall_memories(db, ctx, query=q, limit=limit, mode=mode)
    return AgentRecallResponse(
        query=data["query"],
        session_summaries=data["session_summaries"],
        memory_facts=data["memory_facts"],
        mode=data.get("mode", mode),
    )


@router.get("/memory-context", response_model=AgentMemoryContextOut)
def get_agent_memory_context(
    q: str = "",
    max_chars: int = DEFAULT_MAX_CHARS,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    raw = build_memory_context(db, ctx, hint=q, max_chars=max_chars)
    context = format_memory_block(raw, max_chars=max_chars)
    return AgentMemoryContextOut(
        context=context,
        char_count=len(context),
        max_chars=max_chars,
    )


def _workflow_out(workflow) -> AgentWorkflowOut:
    steps = sorted(workflow.steps, key=lambda s: s.step_index)
    base = AgentWorkflowOut.model_validate(workflow)
    return base.model_copy(update={"steps": [AgentWorkflowStepOut.model_validate(s) for s in steps]})


@router.get("/pipelines")
def get_agent_pipelines(
    ctx: TenantContext = Depends(require_permission("content.create")),
):
    _ = ctx
    return {"pipelines": list_pipelines()}


@router.get("/workflows", response_model=list[AgentWorkflowOut])
def get_agent_workflows(
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    return [_workflow_out(w) for w in list_workflows(db, ctx)]


@router.post("/workflows", response_model=AgentWorkflowOut)
async def post_agent_workflow(
    body: AgentWorkflowCreate,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    workflow = create_workflow(
        db,
        ctx,
        pipeline_code=body.pipeline_code,
        input_data=body.input,
        session_id=body.session_id,
    )
    if body.auto_run:
        workflow = await run_workflow(db, ctx, workflow.id)
    return _workflow_out(workflow)


@router.get("/workflows/{workflow_id}", response_model=AgentWorkflowOut)
def get_agent_workflow(
    workflow_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    return _workflow_out(get_workflow(db, workflow_id, ctx))


@router.post("/workflows/{workflow_id}/run", response_model=AgentWorkflowOut)
async def post_agent_workflow_run(
    workflow_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    workflow = await run_workflow(db, ctx, workflow_id)
    return _workflow_out(workflow)


def _compliance_out(report) -> AgentComplianceReportOut:
    import json

    from app.schemas import AgentComplianceIssueOut

    issues_raw = json.loads(report.issues_json or "[]")
    suggestions = json.loads(report.suggestions_json or "[]")
    return AgentComplianceReportOut(
        report_id=report.id,
        content_id=report.content_id,
        status=report.status,
        issues=[AgentComplianceIssueOut(**item) for item in issues_raw],
        suggestions=suggestions,
        workflow_id=report.workflow_id,
        created_at=report.created_at,
    )


@router.post("/seo/optimize", response_model=AgentSeoOptimizeOut)
async def post_agent_seo_optimize(
    body: AgentSeoOptimizeRequest,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    data = await optimize_metadata(
        db,
        ctx,
        content_id=body.content_id,
        llm_source=body.llm_source,
    )
    return AgentSeoOptimizeOut(
        content_id=body.content_id,
        platform=data["platform"],
        title_candidates=data["title_candidates"],
        tags=data["tags"],
    )


@router.get("/supervisor/agents")
def get_supervisor_agents(
    ctx: TenantContext = Depends(require_permission("content.create")),
):
    _ = ctx
    return {"agents": list_agents()}


@router.get("/supervisor/workflows/{workflow_id}/handoffs")
def get_workflow_supervisor_handoffs(
    workflow_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    handoffs = get_workflow_handoffs(db, workflow_id, ctx)
    return {"workflow_id": str(workflow_id), "handoffs": handoffs}


@router.post("/compliance/check", response_model=AgentComplianceReportOut)
async def post_agent_compliance_check(
    body: AgentComplianceCheckRequest,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    report = await run_compliance_check(
        db,
        ctx,
        content_id=body.content_id,
        workflow_id=body.workflow_id,
        llm_source=body.llm_source,
    )
    return _compliance_out(report)


@router.get("/compliance/reports/{report_id}", response_model=AgentComplianceReportOut)
def get_agent_compliance_report(
    report_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    return _compliance_out(get_compliance_report(db, report_id, ctx))


def _pending_out(row) -> AgentPendingActionOut:
    data = pending_action_to_dict(row)
    return AgentPendingActionOut(
        action_id=UUID(data["action_id"]),
        action_type=data["action_type"],
        status=data["status"],
        content_id=UUID(data["content_id"]),
        summary=data["summary"],
        payload=data.get("payload") or {},
        created_at=row.created_at,
    )


@router.get("/ops/pending", response_model=list[AgentPendingActionOut])
def get_agent_ops_pending(
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    return [_pending_out(row) for row in list_pending_actions(db, ctx)]


@router.post("/ops/actions/{action_id}/confirm", response_model=AgentOpsConfirmOut)
async def post_agent_ops_confirm(
    action_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    result = await confirm_pending_action(db, ctx, action_id)
    scheduled = result.get("scheduled_at")
    return AgentOpsConfirmOut(
        action_id=UUID(result["action_id"]),
        action_type=result["action_type"],
        status=result["status"],
        content_id=UUID(result["content_id"]),
        scheduled_at=datetime.fromisoformat(scheduled.replace("Z", "+00:00")) if scheduled else None,
    )


@router.post("/ops/actions/{action_id}/cancel", response_model=AgentPendingActionOut)
def post_agent_ops_cancel(
    action_id: UUID,
    ctx: TenantContext = Depends(require_permission("content.create")),
    db: Session = Depends(get_db),
):
    return _pending_out(cancel_pending_action(db, ctx, action_id))
