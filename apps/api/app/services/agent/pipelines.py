"""Agent 工作流 Pipeline 定义（C1）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineStepDef:
    step_code: str
    tool_name: str
    agent_code: str = "creator"


PIPELINE_REGISTRY: dict[str, list[PipelineStepDef]] = {
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


def get_pipeline(code: str) -> list[PipelineStepDef]:
    pipeline = PIPELINE_REGISTRY.get(code)
    if not pipeline:
        raise KeyError(code)
    return pipeline


def list_pipelines() -> list[str]:
    return sorted(PIPELINE_REGISTRY.keys())
