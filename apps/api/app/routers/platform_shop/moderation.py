"""P07 违规稽查。对照 PRD 06#p07 · #p07a · #p07b · #p07c · §8.14.4。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.shop_platform import ModerationExportRequest, ShopExportTaskOut
from app.services.permission_service import require_platform_shop_permission
from app.services.shop import p07_moderation_service as p07svc

router = APIRouter(prefix="/moderation-cases", tags=["platform-shop-moderation"])
_perm = require_platform_shop_permission("platform.shop.moderate")


class ForceOffBody(BaseModel):
    reason_type: str | None = None
    reason: str | None = None


class CloseBody(BaseModel):
    resolution: str | None = None
    conclusion: str | None = Field(default=None, min_length=0)
    notify_in_app: bool = False
    notify_sms: bool = False


@router.get("/summary")
def summary(_: User = Depends(_perm), db: Session = Depends(get_db)):
    return p07svc.summary_stats(db)


@router.get("/export")
def export_list(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    case_type: str | None = Query(default=None),
    source: str | None = Query(default=None),
    view: str | None = Query(default=None),
    user: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    csv_text = p07svc.export_list_csv(
        db, user, q=q, status=status, case_type=case_type, source=source, view=view
    )
    payload = "\ufeff" + csv_text
    return StreamingResponse(
        iter([payload.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-moderation-cases.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_export_task(
    body: ModerationExportRequest | None = None,
    user: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    """对照 #p07 · 04#select-common：列表异步导出（站内信本批不接，页内下载）。"""
    return p07svc.create_moderation_export_task(db, user, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_export_task(
    task_id: UUID,
    user: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    return p07svc.get_moderation_export_task(db, user, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_export_file(
    task_id: UUID,
    user: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    csv_text = p07svc.read_moderation_export_file(db, user, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-moderation-cases.csv"'},
    )


@router.get("")
def list_cases(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    case_type: str | None = Query(default=None),
    source: str | None = Query(default=None),
    view: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str | None = Query(default=None),
    sort_dir: str = Query(default="desc"),
    user: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    return p07svc.list_cases(
        db,
        user,
        q=q,
        status=status,
        case_type=case_type,
        source=source,
        view=view,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/{case_id}")
def get_case(case_id: UUID, user: User = Depends(_perm), db: Session = Depends(get_db)):
    return p07svc.get_case(db, user, case_id)


@router.post("/{case_id}/take")
def take(case_id: UUID, user: User = Depends(_perm), db: Session = Depends(get_db)):
    return p07svc.take_case(db, user, case_id)


@router.post("/{case_id}/force-off-sale")
def force_off(
    case_id: UUID,
    body: ForceOffBody | None = None,
    user: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    return p07svc.force_off_sale(
        db,
        user,
        case_id,
        reason_type=body.reason_type if body else None,
        reason=body.reason if body else None,
    )


@router.post("/{case_id}/close")
def close(
    case_id: UUID,
    body: CloseBody | None = None,
    user: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    return p07svc.close_case(
        db,
        user,
        case_id,
        resolution=body.resolution if body else None,
        conclusion=body.conclusion if body else None,
        notify_in_app=bool(body.notify_in_app) if body else False,
        notify_sms=bool(body.notify_sms) if body else False,
    )


@router.post("/{case_id}/attachments")
async def upload_attachment(
    case_id: UUID,
    file: UploadFile = File(...),
    kind: str = Query(default="chat_screenshot"),
    _: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    p07svc._get(db, case_id)
    content = await file.read()
    return p07svc.add_attachment_bytes(
        db,
        case_id,
        filename=file.filename or "file.bin",
        content=content,
        kind=kind,
        content_type=file.content_type,
    )


@router.get("/{case_id}/attachments/{file_id}")
def download_attachment(
    case_id: UUID,
    file_id: str,
    _: User = Depends(_perm),
    db: Session = Depends(get_db),
):
    p07svc._get(db, case_id)
    path = p07svc.resolve_attachment_path(case_id, file_id)
    if not path or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")
    name = path.name.split("_", 1)[-1] if "_" in path.name else path.name
    return FileResponse(path, filename=name, media_type=p07svc.attachment_media_type(path))
