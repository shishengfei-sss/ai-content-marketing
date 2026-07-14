"""通用地址服务。"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import Address

ADDRESS_TYPES = frozenset({"registered", "office", "billing", "shipping", "other"})
ENTITY_TYPES = frozenset({"lead", "customer", "contact", "deal"})


def list_addresses(
    db: Session, tenant_id: UUID, entity_type: str, entity_id: UUID
) -> list[Address]:
    return (
        db.query(Address)
        .filter(
            Address.tenant_id == tenant_id,
            Address.entity_type == entity_type,
            uuid_eq(Address.entity_id, entity_id),
        )
        .order_by(Address.is_default.desc(), Address.created_at.asc())
        .all()
    )


def require_address(db: Session, tenant_id: UUID, address_id: UUID) -> Address:
    row = (
        db.query(Address)
        .filter(uuid_eq(Address.id, address_id), Address.tenant_id == tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="地址不存在")
    return row


def create_address(
    db: Session,
    ctx: TenantContext,
    *,
    entity_type: str,
    entity_id: UUID,
    address: str,
    address_type: str = "office",
    is_default: bool = False,
    province: str | None = None,
    city: str | None = None,
    district: str | None = None,
    zip_code: str | None = None,
    contact_name: str | None = None,
    contact_phone: str | None = None,
) -> Address:
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(status_code=400, detail="不支持的 entity_type")
    if address_type not in ADDRESS_TYPES:
        raise HTTPException(status_code=400, detail="不支持的 address_type")
    if is_default:
        db.query(Address).filter(
            Address.tenant_id == ctx.tenant_id,
            Address.entity_type == entity_type,
            uuid_eq(Address.entity_id, entity_id),
        ).update({"is_default": False})
    row = Address(
        tenant_id=ctx.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        address_type=address_type,
        is_default=is_default,
        province=province,
        city=city,
        district=district,
        address=address.strip(),
        zip_code=zip_code,
        contact_name=contact_name,
        contact_phone=contact_phone,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_address(db: Session, ctx: TenantContext, row: Address, data: dict) -> Address:
    if "address_type" in data and data["address_type"] is not None:
        if data["address_type"] not in ADDRESS_TYPES:
            raise HTTPException(status_code=400, detail="不支持的 address_type")
        row.address_type = data["address_type"]
    for key in ("province", "city", "district", "zip_code", "contact_name", "contact_phone"):
        if key in data and data[key] is not None:
            setattr(row, key, data[key])
    if data.get("address") is not None:
        row.address = str(data["address"]).strip()
    if data.get("is_default") is True:
        db.query(Address).filter(
            Address.tenant_id == ctx.tenant_id,
            Address.entity_type == row.entity_type,
            uuid_eq(Address.entity_id, row.entity_id),
            Address.id != row.id,
        ).update({"is_default": False})
        row.is_default = True
    elif data.get("is_default") is False:
        row.is_default = False
    db.commit()
    db.refresh(row)
    return row


def delete_address(db: Session, ctx: TenantContext, row: Address) -> None:
    db.delete(row)
    db.commit()
