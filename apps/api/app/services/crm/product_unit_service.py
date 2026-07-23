"""产品计量单位服务。"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Product, ProductUnit
from app.schemas.crm_deals import ProductUnitCreate, ProductUnitUpdate

DEFAULT_UNIT_NAMES = ("套", "个", "台", "件", "年", "月", "次", "人天")


def list_units(db: Session, tenant_id: UUID, *, active_only: bool = False) -> list[ProductUnit]:
    q = db.query(ProductUnit).filter(ProductUnit.tenant_id == tenant_id)
    if active_only:
        q = q.filter(ProductUnit.is_active.is_(True))
    return q.order_by(ProductUnit.sort_order.asc(), ProductUnit.name.asc()).all()


def get_unit(db: Session, tenant_id: UUID, unit_id: UUID) -> ProductUnit | None:
    return (
        db.query(ProductUnit)
        .filter(uuid_eq(ProductUnit.id, unit_id), ProductUnit.tenant_id == tenant_id)
        .first()
    )


def _check_name_unique(
    db: Session, tenant_id: UUID, name: str, exclude_id: UUID | None = None
) -> None:
    q = db.query(ProductUnit).filter(ProductUnit.tenant_id == tenant_id, ProductUnit.name == name)
    if exclude_id is not None:
        q = q.filter(ProductUnit.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="单位名称已存在")


def create_unit(db: Session, ctx: TenantContext, data: ProductUnitCreate) -> ProductUnit:
    name = data.name.strip()
    _check_name_unique(db, ctx.tenant_id, name)
    unit = ProductUnit(
        tenant_id=ctx.tenant_id,
        name=name,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def update_unit(db: Session, ctx: TenantContext, unit: ProductUnit, data: ProductUnitUpdate) -> ProductUnit:
    if data.name is not None:
        name = data.name.strip()
        if name != unit.name:
            _check_name_unique(db, ctx.tenant_id, name, exclude_id=unit.id)
            old_name = unit.name
            unit.name = name
            db.query(Product).filter(
                Product.tenant_id == ctx.tenant_id,
                Product.unit == old_name,
                Product.deleted_at.is_(None),
            ).update({Product.unit: name}, synchronize_session=False)
    if data.sort_order is not None:
        unit.sort_order = data.sort_order
    if data.is_active is not None:
        unit.is_active = data.is_active
    db.commit()
    db.refresh(unit)
    return unit


def delete_unit(db: Session, unit: ProductUnit) -> None:
    db.query(Product).filter(
        Product.tenant_id == unit.tenant_id,
        Product.unit == unit.name,
        Product.deleted_at.is_(None),
    ).update({Product.unit: None}, synchronize_session=False)
    db.delete(unit)
    db.commit()


def seed_default_units(db: Session, ctx: TenantContext) -> list[ProductUnit]:
    existing = {u.name for u in list_units(db, ctx.tenant_id)}
    created: list[ProductUnit] = []
    for idx, name in enumerate(DEFAULT_UNIT_NAMES):
        if name in existing:
            continue
        created.append(
            create_unit(
                db,
                ctx,
                ProductUnitCreate(name=name, sort_order=idx, is_active=True),
            )
        )
    return created


def assert_active_unit_name(db: Session, tenant_id: UUID, unit_name: str | None) -> None:
    if not unit_name:
        return
    row = (
        db.query(ProductUnit)
        .filter(
            ProductUnit.tenant_id == tenant_id,
            ProductUnit.name == unit_name.strip(),
            ProductUnit.is_active.is_(True),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=400, detail="请选择有效的产品计量单位")
