"""文档附件 API（v0.8 deal P1-02）。"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import AttachmentOut
from app.services.crm.attachment_service import (
    delete_attachment,
    get_attachment,
    list_attachments,
    upload_attachment,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/attachments", tags=["crm-attachments"])


@router.get("", response_model=list[AttachmentOut])
def list_attachments_endpoint(
    entity_type: str = Query(..., min_length=1, max_length=20),
    entity_id: uuid.UUID = Query(...),
    ctx: TenantContext = Depends(require_permission("crm.deal.view")),
    db: Session = Depends(get_db),
):
    items = list_attachments(db, ctx, entity_type=entity_type, entity_id=entity_id)
    return [AttachmentOut.model_validate(i) for i in items]


@router.post("", response_model=AttachmentOut, status_code=201)
def upload_attachment_endpoint(
    entity_type: str = Query(..., min_length=1, max_length=20),
    entity_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(require_permission("crm.deal.edit")),
    db: Session = Depends(get_db),
):
    att = upload_attachment(
        db, ctx, entity_type=entity_type, entity_id=entity_id, file=file
    )
    return AttachmentOut.model_validate(att)


@router.get("/{attachment_id}/download")
def download_attachment_endpoint(
    attachment_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("crm.deal.view")),
    db: Session = Depends(get_db),
):
    att = get_attachment(db, ctx, attachment_id)
    path = Path(att.storage_path)
    if not path.exists():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="附件文件已丢失")
    return FileResponse(path, filename=att.file_name, media_type=att.file_type or "application/octet-stream")


@router.delete("/{attachment_id}", status_code=204)
def delete_attachment_endpoint(
    attachment_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("crm.deal.edit")),
    db: Session = Depends(get_db),
):
    delete_attachment(db, ctx, attachment_id)
