"""线索公海服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Lead, LeadPool
from app.services.crm.crm_scope_service import assert_can_view_lead


def list_pools(db: Session, tenant_id: UUID) -> list[LeadPool]:
    return db.query(LeadPool).filter(LeadPool.tenant_id == tenant_id).order_by(LeadPool.created_at).all()


def get_pool(db: Session, tenant_id: UUID, pool_id: UUID) -> LeadPool | None:
    return (
        db.query(LeadPool)
        .filter(uuid_eq(LeadPool.id, pool_id), LeadPool.tenant_id == tenant_id)
        .first()
    )


def require_pool(db: Session, tenant_id: UUID, pool_id: UUID) -> LeadPool:
    pool = get_pool(db, tenant_id, pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="公海不存在")
    return pool


def create_pool(
    db: Session,
    ctx: TenantContext,
    *,
    name: str,
    territory_id: UUID | None = None,
    industry_filter: str | None = None,
    auto_reclaim_days: int | None = None,
) -> LeadPool:
    pool = LeadPool(
        tenant_id=ctx.tenant_id,
        name=name.strip(),
        territory_id=territory_id,
        industry_filter=industry_filter,
        auto_reclaim_days=auto_reclaim_days,
    )
    db.add(pool)
    db.commit()
    db.refresh(pool)
    return pool


def update_pool(
    db: Session,
    ctx: TenantContext,
    pool: LeadPool,
    *,
    name: str | None = None,
    territory_id: UUID | None = None,
    industry_filter: str | None = None,
    auto_reclaim_days: int | None = None,
) -> LeadPool:
    if name is not None:
        pool.name = name.strip()
    if territory_id is not None:
        pool.territory_id = territory_id
    if industry_filter is not None:
        pool.industry_filter = industry_filter
    if auto_reclaim_days is not None:
        pool.auto_reclaim_days = auto_reclaim_days
    db.commit()
    db.refresh(pool)
    return pool


def delete_pool(db: Session, ctx: TenantContext, pool: LeadPool) -> None:
    in_use = (
        db.query(Lead)
        .filter(
            Lead.tenant_id == ctx.tenant_id,
            uuid_eq(Lead.pool_id, pool.id),
            Lead.deleted_at.is_(None),
            Lead.owner_user_id.is_(None),
        )
        .count()
    )
    if in_use:
        raise HTTPException(status_code=409, detail="公海内仍有未认领线索，无法删除")
    db.delete(pool)
    db.commit()


def list_pool_leads(db: Session, ctx: TenantContext, pool_id: UUID) -> list[Lead]:
    require_pool(db, ctx.tenant_id, pool_id)
    return (
        db.query(Lead)
        .filter(
            Lead.tenant_id == ctx.tenant_id,
            uuid_eq(Lead.pool_id, pool_id),
            Lead.owner_user_id.is_(None),
            Lead.deleted_at.is_(None),
            Lead.status != "已转化",
        )
        .order_by(Lead.created_at.desc())
        .all()
    )


def reclaim_lead_to_pool(db: Session, ctx: TenantContext, lead: Lead, pool_id: UUID) -> Lead:
    require_pool(db, ctx.tenant_id, pool_id)
    if lead.status == "已转化":
        raise HTTPException(status_code=409, detail="已转化线索不可回收")
    if lead.owner_user_id is not None:
        assert_can_view_lead(ctx, db, lead.owner_user_id, lead.territory_id)
    lead.owner_user_id = None
    lead.pool_id = pool_id
    lead.claimed_at = None
    db.commit()
    db.refresh(lead)
    return lead


def claim_lead(db: Session, ctx: TenantContext, pool_id: UUID, lead_id: UUID) -> Lead:
    require_pool(db, ctx.tenant_id, pool_id)
    lead = (
        db.query(Lead)
        .filter(
            uuid_eq(Lead.id, lead_id),
            Lead.tenant_id == ctx.tenant_id,
            Lead.deleted_at.is_(None),
        )
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    if lead.pool_id != pool_id:
        raise HTTPException(status_code=409, detail="线索不在该公海")
    if lead.owner_user_id is not None:
        raise HTTPException(status_code=409, detail="线索已被认领")
    if lead.status == "已转化":
        raise HTTPException(status_code=409, detail="已转化线索不可认领")
    lead.owner_user_id = ctx.user.id
    lead.claimed_at = datetime.now(timezone.utc)
    from app.services.crm.notification_service import create_notification

    create_notification(
        db,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        title="已认领线索",
        body=f"「{lead.company_name}」已从公海认领",
        category="pool_claim",
        entity_type="lead",
        entity_id=lead.id,
        commit=False,
    )
    db.commit()
    db.refresh(lead)
    return lead
