"""入驻材料落盘路径：按租户目录隔离 file_id。"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status

from app.config import settings

_FILE_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def resolve_onboarding_stored_file(tenant_id: UUID, file_id: str) -> Path | None:
    """按 `{file_id}_{safe_name}` 匹配租户目录；非法标识或不存在则 None。"""
    fid = (file_id or "").strip()
    if not fid or not _FILE_ID_RE.fullmatch(fid):
        return None
    root = Path(settings.STORAGE_DIR) / "shop_onboarding" / str(tenant_id)
    if not root.is_dir():
        return None
    matches = sorted(p for p in root.glob(f"{fid}_*") if p.is_file())
    return matches[0] if matches else None


def assert_onboarding_file_owned(tenant_id: UUID, file_id: str) -> Path:
    fid = (file_id or "").strip()
    if not fid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请先上传文件再识别")
    if not _FILE_ID_RE.fullmatch(fid):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文件标识无效")
    path = resolve_onboarding_stored_file(tenant_id, fid)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在或无权访问")
    return path
