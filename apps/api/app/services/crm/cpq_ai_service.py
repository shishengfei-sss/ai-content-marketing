"""CPQ AI 需求解析（FR-CPQ-06）：仅返回推荐，须人审采纳后才写入配置。"""
from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.schemas.crm_cpq import (
    CpqAiParseOut,
    CpqAiParseRequest,
    CpqAiRecommendation,
)
from app.services.crm.cpq_service import list_params
from app.services.crm.product_service import require_product
from app.services.llm.base import LLMMessage
from app.services.llm_service import llm_service

CPQ_AI_SYSTEM = """你是工业品 CPQ 配置助手。根据客户需求文本与产品可选参数，输出 JSON：
{
  "recommendations": [
    {"param_name": "参数名", "suggested_value": "建议值", "confidence": 0.0到1.0, "reason": "简短理由"}
  ],
  "quantity": null或数字,
  "notes": "可选说明"
}
规则：
1. param_name 必须来自给定参数列表；suggested_value 对 select 类型必须是 options 之一。
2. 无法判断的参数不要编造。
3. 仅输出 JSON，无 markdown。
4. 这是推荐草稿，最终由人工确认。"""


def _heuristic_parse(text: str, params: list) -> tuple[list[CpqAiRecommendation], float | None]:
    """关键词匹配：文本中出现选项名则推荐；抽取数量。"""
    recs: list[CpqAiRecommendation] = []
    qty = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(台|套|件|个|吨|米)", text)
    if m:
        try:
            qty = float(m.group(1))
        except ValueError:
            qty = None

    for p in params:
        name = p.param_name
        if p.param_type == "select" and isinstance(p.options, list):
            # 长选项优先，避免短串误匹配
            opts = sorted([str(o) for o in p.options], key=len, reverse=True)
            hit = next((o for o in opts if o and o in text), None)
            if hit:
                recs.append(
                    CpqAiRecommendation(
                        param_name=name,
                        suggested_value=hit,
                        confidence=0.85,
                        reason=f"需求文本中出现选项「{hit}」",
                    )
                )
        elif p.param_type == "number":
            # 如「功率 55」靠近参数名
            nm = re.escape(name)
            m2 = re.search(rf"{nm}\s*[：:=\-]?\s*(\d+(?:\.\d+)?)", text)
            if m2:
                recs.append(
                    CpqAiRecommendation(
                        param_name=name,
                        suggested_value=m2.group(1),
                        confidence=0.7,
                        reason=f"从文本抽取与「{name}」相邻的数值",
                    )
                )
        elif p.param_type == "text" and name in text:
            # 弱推荐：参数名出现时提示人工填写
            recs.append(
                CpqAiRecommendation(
                    param_name=name,
                    suggested_value="",
                    confidence=0.4,
                    reason=f"文本提到「{name}」，请人工确认取值",
                )
            )
    return recs, qty


def _extract_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # 尝试截取首个 {...}
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    raise HTTPException(status_code=502, detail="AI 解析结果不是合法 JSON")


def _validate_recs(raw_recs: list, params: list) -> list[CpqAiRecommendation]:
    by_name = {p.param_name: p for p in params}
    out: list[CpqAiRecommendation] = []
    for item in raw_recs or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("param_name") or "").strip()
        val = item.get("suggested_value")
        if not name or name not in by_name:
            continue
        p = by_name[name]
        val_str = "" if val is None else str(val).strip()
        if p.param_type == "select":
            opts = [str(o) for o in (p.options or [])]
            if val_str not in opts:
                continue
        conf = item.get("confidence")
        try:
            conf_f = float(conf) if conf is not None else 0.6
        except (TypeError, ValueError):
            conf_f = 0.6
        conf_f = max(0.0, min(1.0, conf_f))
        out.append(
            CpqAiRecommendation(
                param_name=name,
                suggested_value=val_str,
                confidence=conf_f,
                reason=str(item.get("reason") or "AI 推荐")[:200],
            )
        )
    return out


async def parse_requirements(
    db: Session, ctx: TenantContext, req: CpqAiParseRequest
) -> CpqAiParseOut:
    product = require_product(db, ctx, req.product_id)
    if not product.cpq_enabled:
        raise HTTPException(status_code=400, detail="产品未启用 CPQ")
    text = (req.text or "").strip()
    if len(text) < 2:
        raise HTTPException(status_code=400, detail="请粘贴需求文本")

    params = list_params(db, ctx, product.id, include_inactive=False)
    heuristic_recs, heuristic_qty = _heuristic_parse(text, params)

    param_schema = [
        {
            "param_name": p.param_name,
            "param_type": p.param_type,
            "options": p.options if p.param_type == "select" else None,
        }
        for p in params
    ]
    user_payload = json.dumps(
        {"product_name": product.name, "params": param_schema, "requirement_text": text},
        ensure_ascii=False,
    )

    source = "heuristic"
    notes = "基于关键词匹配的推荐草稿，请人工确认后再采纳。"
    recs = heuristic_recs
    qty = heuristic_qty

    try:
        result = await llm_service.chat(
            db,
            ctx.tenant_id,
            [
                LLMMessage(role="system", content=CPQ_AI_SYSTEM),
                LLMMessage(role="user", content=user_payload),
            ],
            llm_source="platform",
            check_platform_quota=False,
        )
        data = _extract_json(result.content)
        llm_recs = _validate_recs(data.get("recommendations") or [], params)
        if llm_recs:
            # 合并：同名以 LLM 为准，其余保留启发式
            by = {r.param_name: r for r in heuristic_recs}
            by.update({r.param_name: r for r in llm_recs})
            recs = list(by.values())
            source = "llm" if result.provider != "fake" else "fake"
            notes = str(data.get("notes") or "AI 推荐草稿，须人审采纳后写入配置。")
        if data.get("quantity") is not None:
            try:
                qty = float(data["quantity"])
            except (TypeError, ValueError):
                pass
    except Exception:
        # LLM 不可用时退回启发式，不阻断
        source = "heuristic"
        notes = "LLM 不可用，已使用关键词匹配推荐；请人工确认。"

    return CpqAiParseOut(
        product_id=product.id,
        recommendations=recs,
        quantity=qty,
        source=source,
        requires_review=True,
        notes=notes,
    )
