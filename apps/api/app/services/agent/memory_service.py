"""Agent 长期记忆 CRUD（LM1）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models import AgentMemoryFact


def _validate_scope_payload(scope: str, *, user_id: UUID | None, tenant_id: UUID | None) -> None:
    if scope == "user":
        if not user_id:
            raise HTTPException(status_code=400, detail="user 范围记忆需要 user_id")
        if tenant_id is not None:
            raise HTTPException(status_code=400, detail="user 范围记忆不应绑定 tenant_id")
    elif scope == "tenant":
        if not tenant_id:
            raise HTTPException(status_code=400, detail="tenant 范围记忆需要 tenant_id")
    else:
        raise HTTPException(status_code=400, detail="scope 必须为 user 或 tenant")


def can_access_memory(ctx: TenantContext, memory: AgentMemoryFact) -> bool:
    if memory.scope == "user":
        return memory.user_id == ctx.user.id
    if memory.scope == "tenant":
        return memory.tenant_id == ctx.tenant_id
    return False


def get_memory(db: Session, memory_id: UUID, ctx: TenantContext) -> AgentMemoryFact:
    memory = db.query(AgentMemoryFact).filter(uuid_eq(AgentMemoryFact.id, memory_id)).first()
    if not memory or not can_access_memory(ctx, memory):
        raise HTTPException(status_code=404, detail="记忆不存在")
    return memory


def list_memories(db: Session, ctx: TenantContext, *, scope: str | None = None) -> list[AgentMemoryFact]:
    scopes = {scope} if scope else {"user", "tenant"}
    if scope and scope not in ("user", "tenant"):
        raise HTTPException(status_code=400, detail="scope 必须为 user 或 tenant")

    items: list[AgentMemoryFact] = []
    if "user" in scopes:
        items.extend(
            db.query(AgentMemoryFact)
            .filter(
                AgentMemoryFact.scope == "user",
                uuid_eq(AgentMemoryFact.user_id, ctx.user.id),
            )
            .order_by(AgentMemoryFact.updated_at.desc())
            .all()
        )
    if "tenant" in scopes:
        items.extend(
            db.query(AgentMemoryFact)
            .filter(
                AgentMemoryFact.scope == "tenant",
                uuid_eq(AgentMemoryFact.tenant_id, ctx.tenant_id),
            )
            .order_by(AgentMemoryFact.updated_at.desc())
            .all()
        )
    return items


def create_memory(
    db: Session,
    ctx: TenantContext,
    *,
    scope: str,
    fact_text: str,
    category: str = "preference",
    source: str = "explicit",
    is_confirmed: bool = True,
) -> AgentMemoryFact:
    text = fact_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="fact_text 不能为空")
    if scope not in ("user", "tenant"):
        raise HTTPException(status_code=400, detail="scope 必须为 user 或 tenant")
    if source not in ("explicit", "inferred"):
        raise HTTPException(status_code=400, detail="source 无效")
    if source == "inferred":
        is_confirmed = False

    user_id = ctx.user.id if scope == "user" else None
    tenant_id = ctx.tenant_id if scope == "tenant" else None
    _validate_scope_payload(scope, user_id=user_id, tenant_id=tenant_id)

    memory = AgentMemoryFact(
        scope=scope,
        user_id=user_id,
        tenant_id=tenant_id,
        category=category.strip() or "preference",
        fact_text=text,
        source=source,
        is_confirmed=is_confirmed,
        created_by=ctx.user.id,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def update_memory(
    db: Session,
    memory_id: UUID,
    ctx: TenantContext,
    *,
    fact_text: str | None = None,
    category: str | None = None,
    is_confirmed: bool | None = None,
) -> AgentMemoryFact:
    memory = get_memory(db, memory_id, ctx)
    if fact_text is not None:
        text = fact_text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="fact_text 不能为空")
        memory.fact_text = text
    if category is not None:
        memory.category = category.strip() or memory.category
    if is_confirmed is not None:
        memory.is_confirmed = is_confirmed
    db.commit()
    db.refresh(memory)
    return memory


def confirm_memory(db: Session, memory_id: UUID, ctx: TenantContext) -> AgentMemoryFact:
    memory = get_memory(db, memory_id, ctx)
    if memory.source != "inferred":
        raise HTTPException(status_code=400, detail="仅推断记忆需要确认")
    if memory.is_confirmed:
        return memory
    memory.is_confirmed = True
    db.commit()
    db.refresh(memory)
    return memory


def delete_memory(db: Session, memory_id: UUID, ctx: TenantContext) -> None:
    memory = get_memory(db, memory_id, ctx)
    db.delete(memory)
    db.commit()
