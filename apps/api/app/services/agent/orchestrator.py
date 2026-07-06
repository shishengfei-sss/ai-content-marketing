"""Agent ReAct 编排：LLM + Tool 多步循环。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models import AgentSession, User
from app.schemas import AgentChatResponse, ContentProposal
from app.services.agent.memory_injection import build_memory_context, format_memory_block
from app.services.agent.session_service import append_message, list_messages
from app.services.agent.tools import _perm_ctx, execute_tool, list_available_tools
from app.services.llm.base import LLMMessage
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

MAX_REACT_STEPS = 8

REACT_SYSTEM_PROMPT = """Agent ReAct
你是营销创作 Agent ReAct 编排器。根据用户目标选择并调用工具，多步完成任务。

每轮仅输出一个 JSON 对象，不要 markdown：
1. 需要调用工具：{"step":"tool_call","tool":"工具名","arguments":{...}}
2. 任务完成：{"step":"done","action":"proposals|generate|chat|clarify|failed","message":"给用户的中文回复"}

规则：
- 先检索知识库再写稿时，先 search_knowledge 再 generate_proposals
- 不得调用 publish_content（发布须用户确认）
- 信息不足时用 action=clarify
- 仅输出 JSON"""


@dataclass
class ReactStep:
    step: str
    tool: str | None = None
    arguments: dict | None = None
    action: str | None = None
    message: str | None = None


def _parse_react_json(raw: str) -> ReactStep:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail="ReAct 解析失败") from e
    return ReactStep(
        step=str(data.get("step") or "done"),
        tool=data.get("tool"),
        arguments=data.get("arguments") or {},
        action=data.get("action"),
        message=data.get("message") or "",
    )


def _summarize_tool_result(tool: str, result: dict) -> str:
    if tool == "search_knowledge":
        n = len(result.get("results") or [])
        return f"检索到 {n} 条知识片段"
    if tool == "generate_proposals":
        n = len(result.get("proposals") or [])
        return f"生成 {n} 个方案"
    if tool == "generate_content":
        return f"正文已生成 content_id={result.get('content_id', '')}"
    if tool in ("publish_content", "schedule_content"):
        if result.get("status") == "pending_confirm":
            return f"待确认{result.get('action_type')} action_id={result.get('action_id')}"
    if tool == "get_quota":
        return f"剩余额度 {result.get('remaining', '?')}"
    preview = json.dumps(result, ensure_ascii=False)
    return preview[:200]


def _build_react_messages(
    session: AgentSession,
    session_goal: str,
    tools: list[dict],
    history: list,
    memory_context: str = "",
) -> list[LLMMessage]:
    parts = [
        f"行业={session.industry_code}",
        f"会话目标={session_goal}",
        f"可用工具={json.dumps(tools, ensure_ascii=False)}",
    ]
    if memory_context.strip():
        parts.append(memory_context.strip())
    tool_results = sum(1 for m in history if m.role == "tool")
    parts.append(f"已完成工具结果数={tool_results}")
    for msg in history[-10:]:
        if msg.role == "user":
            parts.append(f"用户: {msg.content}")
        elif msg.role == "assistant" and msg.message_type == "tool_call":
            meta = json.loads(msg.metadata_json) if msg.metadata_json else {}
            parts.append(f"助手调用工具: {meta.get('tool')}")
        elif msg.role == "tool":
            parts.append(f"工具结果: {msg.content}")
        elif msg.role == "assistant":
            parts.append(f"助手: {msg.content}")
    return [
        LLMMessage(role="system", content=REACT_SYSTEM_PROMPT),
        LLMMessage(role="user", content="\n".join(parts)),
    ]


def _last_tool_proposals(history: list) -> list[ContentProposal] | None:
    for msg in reversed(history):
        if msg.role != "tool" or msg.message_type != "tool_result":
            continue
        if not msg.metadata_json:
            continue
        try:
            meta = json.loads(msg.metadata_json)
            if meta.get("tool") != "generate_proposals":
                continue
            raw = meta.get("result") or {}
            items = raw.get("proposals") or []
            if items:
                return [ContentProposal(**p) for p in items]
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return None


def _last_generated_content(history: list):
    for msg in reversed(history):
        if msg.role != "tool" or not msg.metadata_json:
            continue
        try:
            meta = json.loads(msg.metadata_json)
            if meta.get("tool") == "generate_content":
                return meta.get("result")
        except json.JSONDecodeError:
            continue
    return None


async def handle_react_chat(
    db: Session,
    session: AgentSession,
    user: User,
    tenant_ctx: TenantContext,
    *,
    message: str,
    llm_source: str = "platform",
) -> AgentChatResponse:
    append_message(db, session, role="user", content=message)
    tool_ctx = _perm_ctx(tenant_ctx, db, industry_code=session.industry_code)
    tools = list_available_tools(tool_ctx)
    memory_block = format_memory_block(build_memory_context(db, tenant_ctx, hint=message))

    tool_call_count = 0
    last_proposals: list[ContentProposal] | None = None
    session_goal = message

    for step_idx in range(1, MAX_REACT_STEPS + 1):
        history = list_messages(db, session.id)
        messages = _build_react_messages(session, session_goal, tools, history, memory_block)

        try:
            llm_result = await llm_service.chat(
                db,
                session.tenant_id,
                messages,
                llm_source=llm_source,
                check_platform_quota=False,
            )
        except Exception as e:
            logger.exception("ReAct LLM failed")
            raise HTTPException(status_code=502, detail=f"ReAct 调用失败: {e}") from e

        parsed = _parse_react_json(llm_result.content)

        if parsed.step == "tool_call":
            if not parsed.tool:
                raise HTTPException(status_code=502, detail="ReAct 缺少 tool 名")
            append_message(
                db,
                session,
                role="assistant",
                content=f"调用工具 {parsed.tool}",
                message_type="tool_call",
                metadata={"tool": parsed.tool, "arguments": parsed.arguments or {}},
            )
            result = await execute_tool(tool_ctx, parsed.tool, parsed.arguments or {})
            summary = _summarize_tool_result(parsed.tool, result)
            append_message(
                db,
                session,
                role="tool",
                content=summary,
                message_type="tool_result",
                metadata={"tool": parsed.tool, "result": result},
            )
            tool_call_count += 1
            if parsed.tool == "generate_proposals":
                last_proposals = [ContentProposal(**p) for p in result.get("proposals") or []]
            continue

        if parsed.step == "done":
            action = (parsed.action or "chat").lower()
            reply = parsed.message or "已完成。"
            proposals = last_proposals or _last_tool_proposals(list_messages(db, session.id))
            content_out = None
            if action == "generate":
                gen = _last_generated_content(list_messages(db, session.id))
                if gen and gen.get("content_id"):
                    from app.services.content_service import get_content_for_tenant
                    from app.services.agent.chat_service import _content_out

                    content = get_content_for_tenant(db, UUID(str(gen["content_id"])), session.tenant_id)
                    content_out = _content_out(content)
            assistant = append_message(
                db,
                session,
                role="assistant",
                content=reply,
                message_type=action if action in ("proposals", "content", "clarify") else "text",
                metadata={"react_steps": tool_call_count, "action": action},
            )
            return AgentChatResponse(
                action=action,
                assistant_message=reply,
                clarify_question=reply if action == "clarify" else None,
                proposals=proposals,
                content=content_out,
                message_id=assistant.id,
            )

        raise HTTPException(status_code=502, detail="ReAct 未知 step 类型")

    session.status = "failed"
    db.commit()
    err = "已达到最大推理步数，请简化需求后重试。"
    assistant = append_message(
        db,
        session,
        role="assistant",
        content=err,
        message_type="error",
        metadata={"react_steps": tool_call_count, "max_steps": MAX_REACT_STEPS},
    )
    return AgentChatResponse(
        action="failed",
        assistant_message=err,
        message_id=assistant.id,
    )
