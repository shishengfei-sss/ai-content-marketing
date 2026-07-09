"""Agent 工作流 Pipeline 定义（C1）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineStepDef:
    step_code: str
    tool_name: str
    agent_code: str = "creator"


PIPELINE_REGISTRY: dict[str, list[PipelineStepDef]] = {
    # 交互式创作：前半出方案（暂停等人选），后半写稿+合规（由 resume 追加）
    "content_propose": [
        PipelineStepDef("search", "search_knowledge", "creator"),
        PipelineStepDef("analyze", "analyze_pain_points", "creator"),
        PipelineStepDef("propose", "generate_proposals", "creator"),
    ],
    "content_finish": [
        PipelineStepDef("generate", "generate_content", "creator"),
        PipelineStepDef("optimize", "optimize_content", "creator"),
        PipelineStepDef("compliance", "check_compliance", "compliance"),
        PipelineStepDef("ops", "review_for_publish", "ops"),
    ],
    # 一键全自动（测试/运营），strategy 自动选题
    "content_create": [
        PipelineStepDef("search", "search_knowledge", "creator"),
        PipelineStepDef("analyze", "analyze_pain_points", "creator"),
        PipelineStepDef("strategy", "strategy_proposals", "creator"),
        PipelineStepDef("generate", "generate_content", "creator"),
        PipelineStepDef("optimize", "optimize_content", "creator"),
        PipelineStepDef("compliance", "check_compliance", "compliance"),
        PipelineStepDef("ops", "review_for_publish", "ops"),
    ],
}

# 跑完这些 pipeline 的全部步骤后进入 paused，等待用户选方案
PAUSED_PIPELINES: frozenset[str] = frozenset({"content_propose"})


def get_pipeline(code: str) -> list[PipelineStepDef]:
    pipeline = PIPELINE_REGISTRY.get(code)
    if not pipeline:
        raise KeyError(code)
    return pipeline


def list_pipelines() -> list[str]:
    return sorted(PIPELINE_REGISTRY.keys())
