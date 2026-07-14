"""客户公海服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Customer, CustomerPool
from app.services.crm.crm_scope_service import assert_can_view_customer


def list_pools(db: Session, tenant_id: UUID) -> list[CustomerPool]:
    return (
        db.query(CustomerPool)
        .filter(CustomerPool.tenant_id == tenant_id)
        .order_by(CustomerPool.created_at)
        .all()
    )


def get_pool(db: Session, tenant_id: UUID, pool_id: UUID) -> CustomerPool | None:
    return (
        db.query(CustomerPool)
        .filter(uuid_eq(CustomerPool.id, pool_id), CustomerPool.tenant_id == tenant_id)
        .first()
    )


def require_pool(db: Session, tenant_id: UUID, pool_id: UUID) -> CustomerPool:
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
) -> CustomerPool:
    pool = CustomerPool(
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


def reclaim_customer_to_pool(db: Session, ctx: TenantContext, customer: Customer, pool_id: UUID) -> Customer:
    require_pool(db, ctx.tenant_id, pool_id)
    if customer.owner_user_id is not None:
        assert_can_view_customer(ctx, db, customer.owner_user_id, customer.territory_id)
    customer.owner_user_id = None
    customer.pool_id = pool_id
    customer.claimed_at = None
    db.commit()
    db.refresh(customer)
    return customer


def claim_customer(db: Session, ctx: TenantContext, pool_id: UUID, customer_id: UUID) -> Customer:
    require_pool(db, ctx.tenant_id, pool_id)
    customer = (
        db.query(Customer)
        .filter(
            uuid_eq(Customer.id, customer_id),
            Customer.tenant_id == ctx.tenant_id,
            Customer.deleted_at.is_(None),
        )
        .first()
    )
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    if customer.pool_id != pool_id:
        raise HTTPException(status_code=409, detail="客户不在该公海")
    if customer.owner_user_id is not None:
        raise HTTPException(status_code=409, detail="客户已被认领")
    customer.owner_user_id = ctx.user.id
    customer.claimed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(customer)
    return customer
