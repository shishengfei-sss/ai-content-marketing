"""Supervisor：Creator / Compliance / Ops 路由与 handoff（C5）。"""

from __future__ import annotations

from fastapi import HTTPException

AGENT_CREATOR = "creator"
AGENT_COMPLIANCE = "compliance"
AGENT_OPS = "ops"
AGENT_SEO = "seo"
AGENT_SUPERVISOR = "supervisor"

AGENT_REGISTRY: dict[str, dict] = {
    AGENT_SUPERVISOR: {
        "name": "Supervisor",
        "description": "任务路由与 handoff 协调",
        "allowed_tools": frozenset(),
    },
    AGENT_CREATOR: {
        "name": "Creator",
        "description": "检索、策划、撰写与改稿",
        "allowed_tools": frozenset(
            {
                "search_knowledge",
                "analyze_pain_points",
                "strategy_proposals",
                "generate_proposals",
                "generate_content",
                "optimize_content",
                "revise_content",
                "list_scenes",
                "get_quota",
            }
        ),
    },
    AGENT_COMPLIANCE: {
        "name": "Compliance",
        "description": "合规审查，不执行发布",
        "allowed_tools": frozenset({"check_compliance"}),
    },
    AGENT_OPS: {
        "name": "Ops",
        "description": "发布/排期待确认与就绪检查",
        "allowed_tools": frozenset(
            {
                "review_for_publish",
                "publish_content",
                "schedule_content",
                "get_quota",
            }
        ),
    },
    AGENT_SEO: {
        "name": "Seo",
        "description": "标题候选与平台标签优化",
        "allowed_tools": frozenset({"optimize_metadata"}),
    },
}

TOOL_AGENT_MAP: dict[str, str] = {
    "search_knowledge": AGENT_CREATOR,
    "analyze_pain_points": AGENT_CREATOR,
    "strategy_proposals": AGENT_CREATOR,
    "generate_proposals": AGENT_CREATOR,
    "generate_content": AGENT_CREATOR,
    "optimize_content": AGENT_CREATOR,
    "revise_content": AGENT_CREATOR,
    "list_scenes": AGENT_CREATOR,
    "check_compliance": AGENT_COMPLIANCE,
    "review_for_publish": AGENT_OPS,
    "publish_content": AGENT_OPS,
    "schedule_content": AGENT_OPS,
    "optimize_metadata": AGENT_SEO,
    "get_quota": AGENT_CREATOR,
}


def agent_for_tool(tool_name: str) -> str:
    return TOOL_AGENT_MAP.get(tool_name, AGENT_CREATOR)


def list_agents() -> list[dict]:
    return [
        {"code": code, **{k: v for k, v in meta.items() if k != "allowed_tools"}}
        for code, meta in AGENT_REGISTRY.items()
    ]


def assert_agent_may_run_tool(agent_code: str, tool_name: str) -> None:
    meta = AGENT_REGISTRY.get(agent_code)
    if not meta:
        raise HTTPException(status_code=500, detail=f"未知 Agent: {agent_code}")
    allowed = meta["allowed_tools"]
    if tool_name not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Agent {agent_code} 不可调用工具 {tool_name}",
        )


def decide_after_compliance(status: str) -> dict:
    """Compliance 结束后 Supervisor 决策；block 须交还 Creator 改稿，不可 skip。"""
    normalized = (status or "").strip().lower()
    if normalized == "block":
        return {
            "action": "handoff",
            "from_agent": AGENT_COMPLIANCE,
            "target_agent": AGENT_CREATOR,
            "retry_tool": "revise_content",
            "reason": "compliance_block",
        }
    return {
        "action": "handoff",
        "from_agent": AGENT_COMPLIANCE,
        "target_agent": AGENT_OPS,
        "retry_tool": "review_for_publish",
        "reason": "compliance_pass",
    }


def extract_handoffs(steps: list) -> list[dict]:
    """从步骤 agent_code 序列提取 handoff 记录。"""
    handoffs: list[dict] = []
    prev: str | None = None
    for step in sorted(steps, key=lambda s: s.step_index):
        code = getattr(step, "agent_code", None) or agent_for_tool(step.tool_name)
        if prev and code != prev:
            handoffs.append(
                {
                    "from_agent": prev,
                    "to_agent": code,
                    "step_code": step.step_code,
                    "tool_name": step.tool_name,
                }
            )
        prev = code
    return handoffs
