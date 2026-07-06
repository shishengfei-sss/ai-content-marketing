"""OpsAgent：发布/排期 Confirm 闸（C3）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import AgentComplianceReport, AgentPendingAction, Content
from app.services.content_service import get_content_for_tenant
from app.services.publish_service import execute_publish, schedule_content
from app.services.scope_service import can_view_content

CONFIRMABLE_ACTIONS = frozenset({"publish", "schedule"})


def _dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _load(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _latest_compliance_status(db: Session, content_id: UUID) -> str | None:
    report = (
        db.query(AgentComplianceReport)
        .filter(uuid_eq(AgentComplianceReport.content_id, content_id))
        .order_by(AgentComplianceReport.created_at.desc())
        .first()
    )
    return report.status if report else None


def _ensure_content_access(db: Session, ctx: TenantContext, content_id: UUID) -> Content:
    content = get_content_for_tenant(db, content_id, ctx.tenant_id)
    if not can_view_content(ctx, content.author_id):
        raise HTTPException(status_code=404, detail="内容不存在")
    return content


def _ensure_not_blocked(db: Session, content_id: UUID) -> None:
    status = _latest_compliance_status(db, content_id)
    if status == "block":
        raise HTTPException(status_code=400, detail="内容合规审查未通过，请先修改后再发布")


def create_pending_publish(
    db: Session,
    ctx: TenantContext,
    *,
    content_id: UUID,
    session_id: UUID | None = None,
) -> AgentPendingAction:
    content = _ensure_content_access(db, ctx, content_id)
    _ensure_not_blocked(db, content.id)
    row = AgentPendingAction(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        session_id=session_id,
        content_id=content.id,
        action_type="publish",
        status="pending",
        payload_json="{}",
        summary=f"确认发布公众号内容《{content.topic}》？",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_pending_schedule(
    db: Session,
    ctx: TenantContext,
    *,
    content_id: UUID,
    scheduled_at: datetime,
    session_id: UUID | None = None,
) -> AgentPendingAction:
    content = _ensure_content_access(db, ctx, content_id)
    _ensure_not_blocked(db, content.id)
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    row = AgentPendingAction(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        session_id=session_id,
        content_id=content.id,
        action_type="schedule",
        status="pending",
        payload_json=_dump({"scheduled_at": scheduled_at.isoformat()}),
        summary=f"确认排期发布《{content.topic}》至 {scheduled_at.isoformat()}？",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_pending_actions(db: Session, ctx: TenantContext, *, limit: int = 20) -> list[AgentPendingAction]:
    return (
        db.query(AgentPendingAction)
        .filter(
            uuid_eq(AgentPendingAction.tenant_id, ctx.tenant_id),
            uuid_eq(AgentPendingAction.user_id, ctx.user.id),
            AgentPendingAction.status == "pending",
        )
        .order_by(AgentPendingAction.created_at.desc())
        .limit(min(limit, 50))
        .all()
    )


def get_pending_action(db: Session, action_id: UUID, ctx: TenantContext) -> AgentPendingAction:
    row = (
        db.query(AgentPendingAction)
        .filter(
            uuid_eq(AgentPendingAction.id, action_id),
            uuid_eq(AgentPendingAction.tenant_id, ctx.tenant_id),
            uuid_eq(AgentPendingAction.user_id, ctx.user.id),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="待确认操作不存在")
    return row


def cancel_pending_action(db: Session, ctx: TenantContext, action_id: UUID) -> AgentPendingAction:
    row = get_pending_action(db, action_id, ctx)
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="操作已处理")
    row.status = "cancelled"
    row.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


async def confirm_pending_action(db: Session, ctx: TenantContext, action_id: UUID) -> dict:
    row = get_pending_action(db, action_id, ctx)
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="操作已处理")
    if row.action_type not in CONFIRMABLE_ACTIONS:
        raise HTTPException(status_code=400, detail="不支持的操作类型")

    content = _ensure_content_access(db, ctx, row.content_id)
    _ensure_not_blocked(db, content.id)

    if row.action_type == "publish":
        content = await execute_publish(db, content)
        result = {"content_id": str(content.id), "status": content.status}
    else:
        payload = _load(row.payload_json)
        scheduled_raw = payload.get("scheduled_at")
        if not scheduled_raw:
            raise HTTPException(status_code=400, detail="排期时间缺失")
        scheduled_at = datetime.fromisoformat(str(scheduled_raw).replace("Z", "+00:00"))
        content = schedule_content(db, content, scheduled_at)
        result = {
            "content_id": str(content.id),
            "status": content.status,
            "scheduled_at": content.scheduled_at.isoformat() if content.scheduled_at else None,
        }

    row.status = "confirmed"
    row.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return {
        "action_id": str(row.id),
        "action_type": row.action_type,
        "status": "confirmed",
        "content_id": result.get("content_id"),
        "content_status": result.get("status"),
        "scheduled_at": result.get("scheduled_at"),
    }


def pending_action_to_dict(row: AgentPendingAction) -> dict:
    return {
        "action_id": str(row.id),
        "action_type": row.action_type,
        "status": row.status,
        "content_id": str(row.content_id),
        "summary": row.summary,
        "payload": _load(row.payload_json),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
