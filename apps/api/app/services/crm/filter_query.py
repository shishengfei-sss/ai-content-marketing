"""列表高级筛选 query 参数解析。"""
from __future__ import annotations

import json

from fastapi import HTTPException

from app.schemas.crm_views import ViewFilters


def parse_list_filters_param(raw: str | None) -> dict | None:
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="filters 参数 JSON 无效") from exc
    return ViewFilters.model_validate(data).model_dump()
