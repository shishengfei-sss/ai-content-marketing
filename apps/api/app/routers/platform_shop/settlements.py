"""P05 清结算。对照 PRD 06#p05 · #p05a · #p05b · #p05c · §8.14.3。"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas.shop_platform import SettlementExportRequest, ShopExportTaskOut
from app.services.permission_service import require_platform_shop_permission
from app.services.shop import p05_settlement_service as p05svc

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_SAFE_NAME = re.compile(r"[^\w.\u4e00-\u9fff\-]+")
_VOUCHER_MEDIA = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}

router = APIRouter(prefix="/settlement-batches", tags=["platform-shop-settlement"])
_perm = require_platform_shop_permission("platform.shop.settlement")


class ConfirmBody(BaseModel):
    remark: str | None = None
    transfer_voucher_url: str | None = None


class RetryBody(BaseModel):
    action: str = Field(..., description="retry | return_pending")


class ClosePeriodBody(BaseModel):
    period_end: str | None = None
    delay_days: int | None = None


def _voucher_root(batch_id: UUID) -> Path:
    root = Path(settings.STORAGE_DIR) / "shop_settlement" / str(batch_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_voucher(batch_id: UUID, file_id: str) -> Path | None:
    fid = (file_id or "").strip()
    if not fid or ".." in fid or "/" in fid or "\\" in fid:
        return None
    root = Path(settings.STORAGE_DIR) / "shop_settlement" / str(batch_id)
    if not root.is_dir():
        return None
    matches = sorted(root.glob(f"{fid}_*"))
    return matches[0] if matches else None


@router.get("")
def list_batches(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    view: str | None = Query(default=None),
    period_start: str | None = Query(default=None),
    period_end: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str | None = Query(default=None),
    sort_dir: str = Query(default="desc"),
    _: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    return p05svc.list_batches(
        db,
        q=q,
        status=status,
        view=view,
        period_start=period_start,
        period_end=period_end,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/export")
def export_list(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    view: str | None = Query(default=None),
    period_start: str | None = Query(default=None),
    period_end: str | None = Query(default=None),
    _: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    csv_text = p05svc.export_list_csv(
        db, q=q, status=status, view=view, period_start=period_start, period_end=period_end
    )
    payload = "\ufeff" + csv_text
    return StreamingResponse(
        iter([payload.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-settlement-batches.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_export_task(
    body: SettlementExportRequest | None = None,
    user: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    """对照 #p05：列表导出任务（站内信本批不接，页内下载）。凭证/明细仍同步下载。"""
    return p05svc.create_settlement_export_task(db, user, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_export_task(
    task_id: UUID,
    user: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    return p05svc.get_settlement_export_task(db, user, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_export_file(
    task_id: UUID,
    user: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    csv_text = p05svc.read_settlement_export_file(db, user, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-settlement-batches.csv"'},
    )


@router.post("/close-period")
def close_period(
    body: ClosePeriodBody | None = None,
    _: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    from datetime import date as DateOnly

    period_end = None
    if body and body.period_end:
        period_end = DateOnly.fromisoformat(body.period_end)
    delay = body.delay_days if body and body.delay_days is not None else 7
    return p05svc.close_period(db, period_end=period_end, delay_days=delay)


@router.get("/{batch_id}")
def get_batch(batch_id: UUID, _: User = Depends(_perm), db: Session = Depends(get_db)):
    return p05svc.get_batch(db, batch_id)


@router.post("/{batch_id}/confirm")
def confirm(
    batch_id: UUID,
    body: ConfirmBody | None = None,
    user: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    return p05svc.confirm_payout(
        db,
        user,
        batch_id,
        remark=body.remark if body else None,
        transfer_voucher_url=body.transfer_voucher_url if body else None,
    )


@router.post("/{batch_id}/retry")
def retry(
    batch_id: UUID,
    body: RetryBody,
    user: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    return p05svc.retry_payout(db, user, batch_id, action=body.action)


@router.get("/{batch_id}/export")
def export_voucher(batch_id: UUID, _: User = Depends(_perm), db: Session = Depends(get_db)):
    csv_text = p05svc.export_voucher_csv(db, batch_id)
    payload = "\ufeff" + csv_text
    return StreamingResponse(
        iter([payload.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-settlement-voucher.csv"'},
    )


@router.get("/{batch_id}/export-items")
def export_items(batch_id: UUID, _: User = Depends(_perm), db: Session = Depends(get_db)):
    csv_text = p05svc.export_items_csv(db, batch_id)
    payload = "\ufeff" + csv_text
    return StreamingResponse(
        iter([payload.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-settlement-items.csv"'},
    )


@router.post("/{batch_id}/voucher")
async def upload_voucher(
    batch_id: UUID,
    file: UploadFile = File(...),
    _: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    p05svc._require_batch(db, batch_id)
    raw_name = (file.filename or "voucher.bin").strip() or "voucher.bin"
    safe_name = _SAFE_NAME.sub("_", raw_name)[:120]
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文件为空")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文件不能超过 10MB")
    file_id = str(uuid.uuid4())
    dest = _voucher_root(batch_id) / f"{file_id}_{safe_name}"
    dest.write_bytes(content)
    return {"file_id": file_id, "file_name": safe_name, "size": len(content)}


@router.get("/{batch_id}/voucher/{file_id}")
def download_voucher(
    batch_id: UUID,
    file_id: str,
    _: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    p05svc._require_batch(db, batch_id)
    path = _resolve_voucher(batch_id, file_id)
    if not path or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证文件不存在")
    name = path.name.split("_", 1)[-1] if "_" in path.name else path.name
    media = _VOUCHER_MEDIA.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, filename=name, media_type=media)
