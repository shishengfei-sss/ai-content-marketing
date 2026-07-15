"""合规 block 后的 Supervisor 改稿循环（兼容入口）。

实现已迁至 compliance_revise_service；本模块保持 Workflow import 稳定。
"""
from __future__ import annotations

from app.services.agent.compliance_revise_service import (  # noqa: F401
    MAX_COMPLIANCE_REVISE_ROUNDS,
    build_compliance_revise_instruction as _build_from_service,
    revise_until_pass,
)


def build_compliance_revise_instruction(ctx_data: dict) -> str:
    """Workflow 原签名：仅接收 ctx_data。"""
    return _build_from_service(ctx_data=ctx_data)
