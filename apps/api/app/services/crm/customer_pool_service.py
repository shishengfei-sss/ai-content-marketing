"""客户公海服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Customer, CustomerPool
from app.services.crm.crm_scope_service import assert_can_mutate_customer


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


def update_pool(
    db: Session,
    ctx: TenantContext,
    pool: CustomerPool,
    *,
    name: str | None = None,
    territory_id: UUID | None = None,
    industry_filter: str | None = None,
    auto_reclaim_days: int | None = None,
) -> CustomerPool:
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


def delete_pool(db: Session, ctx: TenantContext, pool: CustomerPool) -> None:
    in_use = (
        db.query(Customer)
        .filter(
            Customer.tenant_id == ctx.tenant_id,
            uuid_eq(Customer.pool_id, pool.id),
            Customer.deleted_at.is_(None),
            Customer.owner_user_id.is_(None),
        )
        .count()
    )
    if in_use:
        raise HTTPException(status_code=409, detail="公海内仍有未认领客户，无法删除")
    db.delete(pool)
    db.commit()


def list_pool_customers(db: Session, ctx: TenantContext, pool_id: UUID) -> list[Customer]:
    require_pool(db, ctx.tenant_id, pool_id)
    return (
        db.query(Customer)
        .filter(
            Customer.tenant_id == ctx.tenant_id,
            uuid_eq(Customer.pool_id, pool_id),
            Customer.owner_user_id.is_(None),
            Customer.deleted_at.is_(None),
        )
        .order_by(Customer.created_at.desc())
        .all()
    )


def reclaim_customer_to_pool(db: Session, ctx: TenantContext, customer: Customer, pool_id: UUID) -> Customer:
    require_pool(db, ctx.tenant_id, pool_id)
    assert_can_mutate_customer(ctx, customer)
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
    if customer.pool_id is None or str(customer.pool_id).replace("-", "").lower() != str(pool_id).replace("-", "").lower():
        raise HTTPException(status_code=409, detail="客户不在该公海")
    if customer.owner_user_id is not None:
        raise HTTPException(status_code=409, detail="客户已被认领")
    customer.owner_user_id = ctx.user.id
    customer.claimed_at = datetime.now(timezone.utc)
    from app.services.crm.sales_org_service import apply_owner_org_snapshot

    snap_territory, snap_manager = apply_owner_org_snapshot(db, ctx.tenant_id, ctx.user.id)
    customer.territory_id = snap_territory
    customer.manager_user_id = snap_manager
    from app.services.crm.notification_service import create_notification

    create_notification(
        db,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        title="已认领客户",
        body=f"「{customer.company_name}」已从公海认领",
        category="pool_claim",
        entity_type="customer",
        entity_id=customer.id,
        commit=False,
    )
    db.commit()
    db.refresh(customer)
    return customer
