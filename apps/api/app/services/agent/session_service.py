"""Agent 会话持久化。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.models import AgentMessage, AgentSession
from app.services.assistant_service import MARKETING_ADVISOR_CODE, normalize_advisor_code


def create_session(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    industry_code: str | None = None,
    title: str = "",
) -> AgentSession:
    code = normalize_advisor_code(industry_code or MARKETING_ADVISOR_CODE)
    session = AgentSession(
        tenant_id=tenant_id,
        user_id=user_id,
        industry_code=code,
        title=title or "新对话",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(
    db: Session,
    session_id: UUID,
    *,
    tenant_id: UUID,
    user_id: UUID | None = None,
) -> AgentSession:
    query = db.query(AgentSession).filter(
        uuid_eq(AgentSession.id, session_id),
        uuid_eq(AgentSession.tenant_id, tenant_id),
    )
    if user_id is not None:
        query = query.filter(uuid_eq(AgentSession.user_id, user_id))
    session = query.first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    code = normalize_advisor_code(session.industry_code)
    if session.industry_code != code:
        session.industry_code = code
        db.commit()
        db.refresh(session)
    return session


def effective_advisor_code(session: AgentSession) -> str:
    return normalize_advisor_code(session.industry_code)


def list_sessions(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    limit: int = 20,
) -> list[AgentSession]:
    return (
        db.query(AgentSession)
        .filter(
            uuid_eq(AgentSession.tenant_id, tenant_id),
            uuid_eq(AgentSession.user_id, user_id),
            AgentSession.status == "active",
        )
        .order_by(AgentSession.updated_at.desc())
        .limit(limit)
        .all()
    )


def append_message(
    db: Session,
    session: AgentSession,
    *,
    role: str,
    content: str,
    message_type: str = "text",
    metadata: dict | None = None,
) -> AgentMessage:
    msg = AgentMessage(
        session_id=session.id,
        role=role,
        content=content,
        message_type=message_type,
        metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
    )
    db.add(msg)
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)
    return msg


def list_messages(db: Session, session_id: UUID) -> list[AgentMessage]:
    return (
        db.query(AgentMessage)
        .filter(uuid_eq(AgentMessage.session_id, session_id))
        .order_by(AgentMessage.created_at.asc())
        .all()
    )
