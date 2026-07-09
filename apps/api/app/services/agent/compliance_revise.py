"""合规 block 后的 Supervisor 改稿循环。"""

from __future__ import annotations

MAX_COMPLIANCE_REVISE_ROUNDS = 3


def build_compliance_revise_instruction(ctx_data: dict) -> str:
    issues = ctx_data.get("_compliance_issues") or []
    suggestions = ctx_data.get("_compliance_suggestions") or []
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
