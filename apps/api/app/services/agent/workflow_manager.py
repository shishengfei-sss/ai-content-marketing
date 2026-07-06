"""Agent WorkflowManager（C1 + C5 Supervisor handoff）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import AgentWorkflow, AgentWorkflowStep
from app.services.agent.pipelines import PIPELINE_REGISTRY, get_pipeline
from app.services.agent.supervisor_service import (
    AGENT_CREATOR,
    assert_agent_may_run_tool,
    decide_after_compliance,
    extract_handoffs,
)
from app.services.agent.tools import _perm_ctx, execute_tool


def _dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _load(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def get_workflow(db: Session, workflow_id: UUID, ctx: TenantContext) -> AgentWorkflow:
    row = (
        db.query(AgentWorkflow)
        .filter(
            uuid_eq(AgentWorkflow.id, workflow_id),
            uuid_eq(AgentWorkflow.tenant_id, ctx.tenant_id),
            uuid_eq(AgentWorkflow.user_id, ctx.user.id),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return row


def list_workflows(db: Session, ctx: TenantContext, *, limit: int = 20) -> list[AgentWorkflow]:
    return (
        db.query(AgentWorkflow)
        .filter(
            uuid_eq(AgentWorkflow.tenant_id, ctx.tenant_id),
            uuid_eq(AgentWorkflow.user_id, ctx.user.id),
        )
        .order_by(AgentWorkflow.created_at.desc())
        .limit(min(limit, 50))
        .all()
    )


def create_workflow(
    db: Session,
    ctx: TenantContext,
    *,
    pipeline_code: str,
    input_data: dict,
    session_id: UUID | None = None,
) -> AgentWorkflow:
    if pipeline_code not in PIPELINE_REGISTRY:
        raise HTTPException(status_code=400, detail=f"未知 pipeline: {pipeline_code}")
    if pipeline_code == "content_create":
        for key in ("platform", "topic"):
            if not str(input_data.get(key) or "").strip():
                raise HTTPException(status_code=400, detail=f"缺少参数 {key}")

    steps_def = get_pipeline(pipeline_code)
    workflow = AgentWorkflow(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        session_id=session_id,
        pipeline_code=pipeline_code,
        status="pending",
        current_step=0,
        input_json=_dump(input_data),
    )
    db.add(workflow)
    db.flush()
    for idx, step in enumerate(steps_def):
        db.add(
            AgentWorkflowStep(
                workflow_id=workflow.id,
                step_index=idx,
                step_code=step.step_code,
                tool_name=step.tool_name,
                agent_code=step.agent_code,
                status="pending",
            )
        )
    db.commit()
    db.refresh(workflow)
    return workflow


def get_workflow_handoffs(db: Session, workflow_id: UUID, ctx: TenantContext) -> list[dict]:
    workflow = get_workflow(db, workflow_id, ctx)
    handoffs = extract_handoffs(workflow.steps)
    extra = _load(workflow.output_json).get("supervisor_handoffs") or []
    return handoffs + extra


def _build_tool_args(step: AgentWorkflowStep, workflow: AgentWorkflow, ctx_data: dict) -> dict:
    industry = ctx_data.get("industry_code") or "finance"
    llm_source = ctx_data.get("llm_source") or "platform"
    platform = ctx_data.get("platform") or "wechat"
    topic = ctx_data.get("topic") or ""
    scene = ctx_data.get("scene") or "bookkeeping_intro"
    content_format = ctx_data.get("content_format") or "article"

    if step.tool_name == "search_knowledge":
        return {
            "query": ctx_data.get("search_query") or topic,
            "industry_code": industry,
            "limit": 5,
        }
    if step.tool_name == "analyze_pain_points":
        return {
            "platform": platform,
            "scene": scene,
            "topic": topic,
            "industry_code": industry,
            "llm_source": llm_source,
            "knowledge_results": ctx_data.get("_knowledge_results"),
        }
    if step.tool_name == "strategy_proposals":
        return {
            "platform": platform,
            "scene": scene,
            "topic": topic,
            "content_format": content_format,
            "industry_code": industry,
            "llm_source": llm_source,
            "pain_analysis": ctx_data.get("_pain_analysis"),
        }
    if step.tool_name == "generate_content":
        selected = ctx_data.get("_selected_proposal") or {"title": topic, "angle": "", "outline": ""}
        instruction_parts: list[str] = []
        if ctx_data.get("_pain_analysis"):
            instruction_parts.append(
                "痛点分析：" + json.dumps(ctx_data["_pain_analysis"], ensure_ascii=False)
            )
        if ctx_data.get("_selection_rationale"):
            instruction_parts.append("选题理由：" + str(ctx_data["_selection_rationale"]))
        return {
            "platform": platform,
            "scene": scene,
            "topic": topic,
            "content_format": content_format,
            "selected_proposal": selected,
            "industry_code": industry,
            "llm_source": llm_source,
            "ephemeral_instruction": "\n".join(instruction_parts),
        }
    if step.tool_name == "optimize_content":
        content_id = ctx_data.get("content_id")
        if not content_id:
            raise HTTPException(status_code=500, detail="缺少 content_id，无法优化")
        return {
            "content_id": content_id,
            "llm_source": llm_source,
            "pain_analysis": ctx_data.get("_pain_analysis"),
        }
    if step.tool_name == "check_compliance":
        content_id = ctx_data.get("content_id")
        if not content_id:
            raise HTTPException(status_code=500, detail="缺少 content_id，无法合规审查")
        return {
            "content_id": content_id,
            "workflow_id": str(workflow.id),
            "llm_source": llm_source,
        }
    if step.tool_name == "review_for_publish":
        content_id = ctx_data.get("content_id")
        if not content_id:
            raise HTTPException(status_code=500, detail="缺少 content_id，无法 Ops 检查")
        return {"content_id": content_id}
    if step.tool_name == "revise_content":
        content_id = ctx_data.get("content_id")
        if not content_id:
            raise HTTPException(status_code=500, detail="缺少 content_id，无法改稿")
        suggestions = ctx_data.get("_compliance_suggestions") or ["请修正合规问题"]
        return {
            "content_id": content_id,
            "instruction": "；".join(suggestions),
            "llm_source": llm_source,
        }
    if step.tool_name == "generate_proposals":
        return {
            "platform": platform,
            "scene": scene,
            "topic": topic,
            "content_format": content_format,
            "industry_code": industry,
            "llm_source": llm_source,
        }
    raise HTTPException(status_code=500, detail=f"未配置工具参数: {step.tool_name}")


def _apply_step_result(step: AgentWorkflowStep, workflow: AgentWorkflow, ctx_data: dict, result: dict) -> None:
    if step.tool_name == "search_knowledge":
        ctx_data["_knowledge_results"] = result.get("results") or []
    elif step.tool_name == "analyze_pain_points":
        ctx_data["_pain_analysis"] = result
    elif step.tool_name == "strategy_proposals":
        ctx_data["_proposals"] = result.get("proposals") or []
        ctx_data["_selected_proposal"] = result.get("selected_proposal")
        ctx_data["_selection_rationale"] = result.get("selection_rationale")
    elif step.tool_name == "generate_proposals":
        ctx_data["_proposals"] = result.get("proposals") or []
    elif step.tool_name == "generate_content":
        ctx_data["content_id"] = result.get("content_id")
        ctx_data["_topic"] = result.get("topic")
    elif step.tool_name == "optimize_content":
        ctx_data["content_id"] = result.get("content_id")
        ctx_data["_body_preview"] = result.get("body_preview")
    elif step.tool_name == "revise_content":
        ctx_data["content_id"] = result.get("content_id")
        ctx_data["_body_preview"] = result.get("body_preview")
    elif step.tool_name == "check_compliance":
        ctx_data["_compliance"] = result
        ctx_data["_compliance_suggestions"] = result.get("suggestions") or []
    elif step.tool_name == "review_for_publish":
        ctx_data["_ops_review"] = result

    if step.tool_name in ("check_compliance", "review_for_publish") or step.tool_name == "revise_content":
        workflow.output_json = _dump(
            {
                "content_id": ctx_data.get("content_id"),
                "topic": ctx_data.get("_topic") or ctx_data.get("topic"),
                "body_preview": ctx_data.get("_body_preview"),
                "pain_analysis": ctx_data.get("_pain_analysis"),
                "proposals": ctx_data.get("_proposals"),
                "selection_rationale": ctx_data.get("_selection_rationale"),
                "compliance": ctx_data.get("_compliance"),
                "ops_review": ctx_data.get("_ops_review"),
                "supervisor_handoffs": ctx_data.get("_supervisor_handoffs") or [],
            }
        )


async def _run_tool_step(
    db: Session,
    tool_ctx,
    step: AgentWorkflowStep,
    workflow: AgentWorkflow,
    ctx_data: dict,
) -> dict:
    args = _build_tool_args(step, workflow, ctx_data)
    assert_agent_may_run_tool(step.agent_code, step.tool_name)
    step.status = "running"
    step.input_json = _dump(args)
    step.started_at = datetime.now(timezone.utc)
    db.commit()
    try:
        result = await execute_tool(tool_ctx, step.tool_name, args)
    except HTTPException as exc:
        step.status = "failed"
        step.error_message = str(exc.detail)
        step.finished_at = datetime.now(timezone.utc)
        workflow.status = "failed"
        workflow.error_message = step.error_message
        workflow.current_step = step.step_index
        db.commit()
        raise
    except Exception as exc:
        step.status = "failed"
        step.error_message = str(exc)
        step.finished_at = datetime.now(timezone.utc)
        workflow.status = "failed"
        workflow.error_message = step.error_message
        workflow.current_step = step.step_index
        db.commit()
        raise

    step.status = "completed"
    step.output_json = _dump(result)
    step.finished_at = datetime.now(timezone.utc)
    workflow.current_step = step.step_index + 1
    _apply_step_result(step, workflow, ctx_data, result)
    db.commit()
    return result


async def run_workflow(db: Session, ctx: TenantContext, workflow_id: UUID) -> AgentWorkflow:
    workflow = get_workflow(db, workflow_id, ctx)
    if workflow.status == "completed":
        return workflow
    if workflow.status == "failed":
        raise HTTPException(status_code=400, detail="工作流已失败，请新建")

    tool_ctx = _perm_ctx(ctx, db, industry_code=_load(workflow.input_json).get("industry_code") or "finance")
    ctx_data = _load(workflow.input_json)
    ctx_data.setdefault("_supervisor_handoffs", [])
    workflow.status = "running"
    db.commit()

    steps = sorted(workflow.steps, key=lambda s: s.step_index)
    for step in steps:
        if step.status == "completed":
            continue
        if step.status == "failed":
            workflow.status = "failed"
            workflow.error_message = step.error_message
            db.commit()
            return workflow

        try:
            result = await _run_tool_step(db, tool_ctx, step, workflow, ctx_data)
        except (HTTPException, Exception):
            db.refresh(workflow)
            return workflow

        if step.tool_name == "check_compliance":
            decision = decide_after_compliance(str(result.get("status") or ""))
            ctx_data["_supervisor_handoffs"].append(decision)
            if decision.get("reason") == "compliance_block" and not ctx_data.get("_compliance_revised"):
                ctx_data["_compliance_revised"] = True
                revise_step = AgentWorkflowStep(
                    workflow_id=workflow.id,
                    step_index=len(steps) + 100,
                    step_code="supervisor_revise",
                    tool_name="revise_content",
                    agent_code=AGENT_CREATOR,
                    status="pending",
                )
                db.add(revise_step)
                db.commit()
                db.refresh(workflow)
                try:
                    await _run_tool_step(db, tool_ctx, revise_step, workflow, ctx_data)
                except (HTTPException, Exception):
                    db.refresh(workflow)
                    return workflow

                recheck_step = AgentWorkflowStep(
                    workflow_id=workflow.id,
                    step_index=len(steps) + 101,
                    step_code="supervisor_recheck",
                    tool_name="check_compliance",
                    agent_code=step.agent_code,
                    status="pending",
                )
                db.add(recheck_step)
                db.commit()
                db.refresh(workflow)
                try:
                    recheck_result = await _run_tool_step(db, tool_ctx, recheck_step, workflow, ctx_data)
                except (HTTPException, Exception):
                    db.refresh(workflow)
                    return workflow
                if str(recheck_result.get("status") or "") == "block":
                    workflow.status = "failed"
                    workflow.error_message = "合规 block 未通过，Supervisor 已交还 Creator 改稿但仍未通过"
                    db.commit()
                    db.refresh(workflow)
                    return workflow

    workflow.status = "completed"
    if not workflow.output_json:
        workflow.output_json = _dump({"steps_completed": len(steps)})
    db.commit()
    db.refresh(workflow)
    return workflow
