"""商家端列表导出任务落盘。对照 01#a13 / #a09（站内信本批不接，页内下载）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.shop import ShopExportTask
from app.schemas.shop_platform import ShopExportTaskOut


def _now() -> datetime:
    return datetime.now(timezone.utc)


def task_out(row: ShopExportTask) -> ShopExportTaskOut:
    return ShopExportTaskOut(
        id=row.id,
        resource=row.resource,
        status=row.status,
        file_name=row.file_name,
        row_count=int(row.row_count or 0),
        error=row.error,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


class _UserOwner:
    """平台端无 TenantContext 时，用运营账号所属租户落盘导出任务。"""

    def __init__(self, user):
        if not getattr(user, "tenant_id", None):
            raise HTTPException(status_code=422, detail="无法确定导出归属")
        self.tenant_id = user.tenant_id
        self.user = user


def persist_csv_for_user(db: Session, user, **kwargs) -> ShopExportTaskOut:
    return persist_csv_task(db, _UserOwner(user), **kwargs)


def get_task_for_user(db: Session, user, task_id: UUID, resource: str) -> ShopExportTaskOut:
    return get_task(db, _UserOwner(user), task_id, resource)


def read_file_for_user(db: Session, user, task_id: UUID, resource: str) -> str:
    return read_file(db, _UserOwner(user), task_id, resource)


def persist_csv_task(
    db: Session,
    ctx: TenantContext,
    *,
    resource: str,
    file_name: str,
    csv_text: str,
    filters: dict | None = None,
    row_count: int | None = None,
) -> ShopExportTaskOut:
    task_id = uuid.uuid4()
    rel = Path("shop_exports") / str(ctx.tenant_id) / f"{task_id}.csv"
    abs_path = Path(settings.STORAGE_DIR) / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(csv_text, encoding="utf-8")
    now = _now()
    counted = row_count
    if counted is None:
        counted = max(0, csv_text.count("\n"))
        if csv_text.endswith("\n"):
            counted = max(0, counted - 1)
    row = ShopExportTask(
        id=task_id,
        tenant_id=ctx.tenant_id,
        operator_id=ctx.user.id,
        resource=resource,
        status="done",
        filters_json={k: v for k, v in (filters or {}).items() if v not in (None, "")},
        file_name=file_name,
        file_path=str(rel).replace("\\", "/"),
        row_count=counted,
        created_at=now,
        finished_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return task_out(row)


def get_task(
    db: Session, ctx: TenantContext, task_id: UUID, resource: str
) -> ShopExportTaskOut:
    row = (
        db.query(ShopExportTask)
        .filter(
            uuid_eq(ShopExportTask.id, task_id),
            uuid_eq(ShopExportTask.tenant_id, ctx.tenant_id),
            ShopExportTask.resource == resource,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="导出任务不存在")
    return task_out(row)


def read_file(db: Session, ctx: TenantContext, task_id: UUID, resource: str) -> str:
    row = (
        db.query(ShopExportTask)
        .filter(
            uuid_eq(ShopExportTask.id, task_id),
            uuid_eq(ShopExportTask.tenant_id, ctx.tenant_id),
            ShopExportTask.resource == resource,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="导出任务不存在")
    if row.status != "done" or not row.file_path:
        raise HTTPException(status_code=409, detail="导出尚未完成")
    path = Path(settings.STORAGE_DIR) / row.file_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="导出文件不存在")
    return path.read_text(encoding="utf-8")
