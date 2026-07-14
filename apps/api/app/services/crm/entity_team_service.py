"""通用实体协作团队。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import DealTeamMember, EntityTeamMember

ENTITY_TYPES = frozenset({"lead", "customer", "deal", "contact"})


def list_members(
    db: Session, tenant_id: UUID, entity_type: str, entity_id: UUID
) -> list[EntityTeamMember]:
    return (
        db.query(EntityTeamMember)
        .filter(
            EntityTeamMember.tenant_id == tenant_id,
            EntityTeamMember.entity_type == entity_type,
            uuid_eq(EntityTeamMember.entity_id, entity_id),
        )
        .order_by(EntityTeamMember.joined_at.asc())
        .all()
    )


def add_member(
    db: Session,
    ctx: TenantContext,
    *,
    entity_type: str,
    entity_id: UUID,
    user_id: UUID,
    role: str = "member",
) -> EntityTeamMember:
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(status_code=400, detail="不支持的 entity_type")
    existing = (
        db.query(EntityTeamMember)
        .filter(
            EntityTeamMember.tenant_id == ctx.tenant_id,
            EntityTeamMember.entity_type == entity_type,
            uuid_eq(EntityTeamMember.entity_id, entity_id),
            uuid_eq(EntityTeamMember.user_id, user_id),
        )
        .first()
    )
    if existing:
        existing.role = role or existing.role
        # 同步 deal_team_members
        if entity_type == "deal":
            _sync_deal_member(db, ctx, entity_id, user_id, existing.role, create=False)
        db.commit()
        db.refresh(existing)
        return existing
    row = EntityTeamMember(
        tenant_id=ctx.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        role=role or "member",
    )
    db.add(row)
    if entity_type == "deal":
        _sync_deal_member(db, ctx, entity_id, user_id, row.role, create=True)
    db.commit()
    db.refresh(row)
    return row


def remove_member(db: Session, ctx: TenantContext, member_id: UUID) -> None:
    row = (
        db.query(EntityTeamMember)
        .filter(uuid_eq(EntityTeamMember.id, member_id), EntityTeamMember.tenant_id == ctx.tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="成员不存在")
    if row.entity_type == "deal":
        dtm = (
            db.query(DealTeamMember)
            .filter(
                DealTeamMember.tenant_id == ctx.tenant_id,
                uuid_eq(DealTeamMember.deal_id, row.entity_id),
                uuid_eq(DealTeamMember.user_id, row.user_id),
            )
            .first()
        )
        if dtm:
            db.delete(dtm)
    db.delete(row)
    db.commit()


def _sync_deal_member(
    db: Session,
    ctx: TenantContext,
    deal_id: UUID,
    user_id: UUID,
    role: str,
    *,
    create: bool,
) -> None:
    existing = (
        db.query(DealTeamMember)
        .filter(
            DealTeamMember.tenant_id == ctx.tenant_id,
            uuid_eq(DealTeamMember.deal_id, deal_id),
            uuid_eq(DealTeamMember.user_id, user_id),
        )
        .first()
    )
    if existing:
        existing.role = role
        return
    if create:
        db.add(
            DealTeamMember(
                tenant_id=ctx.tenant_id,
                deal_id=deal_id,
                user_id=user_id,
                role=role,
            )
        )


def ensure_deal_owner_synced(db: Session, ctx: TenantContext, deal_id: UUID, owner_user_id: UUID) -> None:
    """创建商机后保证通用表也有 owner。"""
    existing = (
        db.query(EntityTeamMember)
        .filter(
            EntityTeamMember.tenant_id == ctx.tenant_id,
            EntityTeamMember.entity_type == "deal",
            uuid_eq(EntityTeamMember.entity_id, deal_id),
            uuid_eq(EntityTeamMember.user_id, owner_user_id),
        )
        .first()
    )
    if existing:
        return
    db.add(
        EntityTeamMember(
            tenant_id=ctx.tenant_id,
            entity_type="deal",
            entity_id=deal_id,
            user_id=owner_user_id,
            role="owner",
        )
    )
    db.flush()
