"""统一通知中心。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Notification


def create_notification(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    title: str,
    body: str | None = None,
    category: str = "system",
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    commit: bool = False,
) -> Notification | None:
    if not user_id:
        return None
    row = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        category=category,
        title=title[:200],
        body=body,
        entity_type=entity_type,
        entity_id=entity_id,
        is_read=False,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


def notify_user(
    db: Session,
    ctx: TenantContext,
    user_id: UUID,
    *,
    title: str,
    body: str | None = None,
    category: str = "crm",
    entity_type: str | None = None,
    entity_id: UUID | None = None,
) -> Notification | None:
    if user_id == ctx.user.id:
        # 自己触发的操作通常不通知自己（认领可通知）
        if category != "pool_claim":
            return None
    return create_notification(
        db,
        tenant_id=ctx.tenant_id,
        user_id=user_id,
        title=title,
        body=body,
        category=category,
        entity_type=entity_type,
        entity_id=entity_id,
        commit=False,
    )


def list_notifications(
    db: Session,
    ctx: TenantContext,
    *,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Notification], int]:
    q = db.query(Notification).filter(
        Notification.tenant_id == ctx.tenant_id,
        uuid_eq(Notification.user_id, ctx.user.id),
    )
    if unread_only:
        q = q.filter(Notification.is_read.is_(False))
    total = q.count()
    items = (
        q.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def unread_count(db: Session, ctx: TenantContext) -> int:
    return (
        db.query(Notification)
        .filter(
            Notification.tenant_id == ctx.tenant_id,
            uuid_eq(Notification.user_id, ctx.user.id),
            Notification.is_read.is_(False),
        )
        .count()
    )


def mark_read(db: Session, ctx: TenantContext, notification_id: UUID) -> Notification:
    row = (
        db.query(Notification)
        .filter(
            uuid_eq(Notification.id, notification_id),
            Notification.tenant_id == ctx.tenant_id,
            uuid_eq(Notification.user_id, ctx.user.id),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="通知不存在")
    row.is_read = True
    row.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def mark_all_read(db: Session, ctx: TenantContext) -> int:
    now = datetime.now(timezone.utc)
    q = db.query(Notification).filter(
        Notification.tenant_id == ctx.tenant_id,
        uuid_eq(Notification.user_id, ctx.user.id),
        Notification.is_read.is_(False),
    )
    count = q.count()
    q.update({"is_read": True, "read_at": now})
    db.commit()
    return count
