"""通用地址 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import AddressCreate, AddressOut, AddressUpdate
from app.services.crm import address_service
from app.services.permission_service import require_any_permission

router = APIRouter(prefix="/addresses", tags=["crm-addresses"])

_VIEW = require_any_permission(
    "crm.customer.edit",
    "crm.lead.edit",
    "crm.deal.edit",
    "crm.customer.list_own",
    "crm.lead.list_own",
    "crm.deal.list_own",
)
_EDIT = require_any_permission("crm.customer.edit", "crm.lead.edit", "crm.deal.edit")


@router.get("", response_model=list[AddressOut])
def api_list(
    entity_type: str = Query(...),
    entity_id: UUID = Query(...),
    ctx: TenantContext = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    return address_service.list_addresses(db, ctx.tenant_id, entity_type, entity_id)


@router.post("", response_model=AddressOut, status_code=201)
def api_create(
    body: AddressCreate,
    ctx: TenantContext = Depends(_EDIT),
    db: Session = Depends(get_db),
):
    return address_service.create_address(
        db,
        ctx,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        address=body.address,
        address_type=body.address_type,
        is_default=body.is_default,
        province=body.province,
        city=body.city,
        district=body.district,
        zip_code=body.zip_code,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
    )


@router.put("/{address_id}", response_model=AddressOut)
def api_update(
    address_id: UUID,
    body: AddressUpdate,
    ctx: TenantContext = Depends(_EDIT),
    db: Session = Depends(get_db),
):
    row = address_service.require_address(db, ctx.tenant_id, address_id)
    return address_service.update_address(db, ctx, row, body.model_dump(exclude_unset=True))


@router.delete("/{address_id}", status_code=204)
def api_delete(
    address_id: UUID,
    ctx: TenantContext = Depends(_EDIT),
    db: Session = Depends(get_db),
):
    row = address_service.require_address(db, ctx.tenant_id, address_id)
    address_service.delete_address(db, ctx, row)
