"""商家端内容文件上传（A05/A06）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import ContentFileUploadOut
from app.services.permission_service import require_permission
from app.services.shop import content_cms_service

router = APIRouter(prefix="/content/files", tags=["shop-content-files"])


@router.post("", response_model=ContentFileUploadOut)
async def upload_file(
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(require_permission("shop.content.write")),
    db: Session = Depends(get_db),
):
    return content_cms_service.upload_content_file(db, ctx, file)


@router.get("/{file_id}")
def download_file(
    file_id: str,
    ctx: TenantContext = Depends(require_permission("shop.content.read")),
    db: Session = Depends(get_db),
):
    path = content_cms_service.resolve_content_file_path(ctx.tenant_id, file_id)
    if not path or not path.is_file():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=path.name.split("_", 1)[-1])
