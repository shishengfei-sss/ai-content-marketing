"""文档附件（本地文件存储，预留对象存储接口）。"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, status, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import TenantContext
from app.models.crm import Attachment, Deal

ATTACHMENT_ENTITY_TYPES = {"deal", "customer", "lead", "quote", "contract", "order"}

_MAX_SIZE = 50 * 1024 * 1024  # 50MB


def _attachment_root() -> Path:
    root = Path(settings.ATTACHMENT_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _assert_can_access_entity(ctx: TenantContext, db: Session, entity_type: str, entity_id: uuid.UUID) -> None:
    if entity_type == "deal":
        deal = db.query(Deal).filter(Deal.id == entity_id, Deal.tenant_id == ctx.tenant_id).first()
        if not deal:
            raise HTTPException(status_code=404, detail="商机不存在")
        from app.services.crm.crm_scope_service import assert_can_view_deal

        assert_can_view_deal(ctx, db, deal.owner_user_id, deal.territory_id)
    else:
        # 其它实体暂以租户内可见为基线，不做细粒度校验
        pass


def upload_attachment(
    db: Session,
    ctx: TenantContext,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    file: UploadFile,
) -> Attachment:
    if entity_type not in ATTACHMENT_ENTITY_TYPES:
        raise HTTPException(status_code=422, detail=f"不支持的实体类型: {entity_type}")
    _assert_can_access_entity(ctx, db, entity_type, entity_id)

    file_name = (file.filename or "未命名").strip()
    if not file_name:
        file_name = "未命名"
    # 读取内容（限制大小）
    stream: BinaryIO = file.file
    data = stream.read(_MAX_SIZE + 1)
    if len(data) > _MAX_SIZE:
        raise HTTPException(status_code=413, detail="文件超过 50MB 限制")

    storage_name = f"{uuid.uuid4().hex}_{file_name}"
    storage_path = _attachment_root() / storage_name
    storage_path.write_bytes(data)

    attachment = Attachment(
        tenant_id=ctx.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        file_name=file_name,
        file_size=len(data),
        file_type=file.content_type or None,
        storage_path=str(storage_path),
        uploaded_by_user_id=ctx.user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def list_attachments(
    db: Session,
    ctx: TenantContext,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
) -> list[Attachment]:
    _assert_can_access_entity(ctx, db, entity_type, entity_id)
    return (
        db.query(Attachment)
        .filter(
            Attachment.tenant_id == ctx.tenant_id,
            Attachment.entity_type == entity_type,
            Attachment.entity_id == entity_id,
        )
        .order_by(Attachment.created_at.desc())
        .all()
    )


def get_attachment(db: Session, ctx: TenantContext, attachment_id: uuid.UUID) -> Attachment:
    att = db.query(Attachment).filter(
        Attachment.id == attachment_id, Attachment.tenant_id == ctx.tenant_id
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")
    _assert_can_access_entity(ctx, db, att.entity_type, att.entity_id)
    return att


def delete_attachment(db: Session, ctx: TenantContext, attachment_id: uuid.UUID) -> None:
    att = get_attachment(db, ctx, attachment_id)
    is_admin = ctx.membership.role.is_system and ctx.membership.role.code == "admin"
    if att.uploaded_by_user_id != ctx.user.id and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该附件")
    try:
        Path(att.storage_path).unlink(missing_ok=True)
    except OSError:
        pass
    db.delete(att)
    db.commit()


def attachment_file_path(att: Attachment) -> Path:
    p = Path(att.storage_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="附件文件已丢失")
    return p
