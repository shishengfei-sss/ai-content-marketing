"""商家端列表导出条数上限。对照 PRD 01-管理端UI 列表导出 ≤5000。"""

from __future__ import annotations

from fastapi import HTTPException

SHOP_EXPORT_ROW_LIMIT = 5000
EXPORT_TOO_MANY_MSG = "结果过多，请缩小筛选"


def assert_export_within_limit(total: int, *, limit: int = SHOP_EXPORT_ROW_LIMIT) -> None:
    if int(total or 0) > limit:
        raise HTTPException(status_code=422, detail=EXPORT_TOO_MANY_MSG)
