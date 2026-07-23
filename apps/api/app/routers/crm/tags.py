"""标签 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import EntityTagBind, EntityTagOut, TagCreate, TagOut, TagUpdate
from app.services.crm import tag_service
from app.services.permission_service import require_any_permission

router = APIRouter(tags=["crm-tags"])

_VIEW = require_any_permission(
    "crm.customer.view",
    "crm.lead.view",
    "crm.deal.view",
    "crm.quote.view",
    "crm.contract.view",
    "crm.payment.view",
    "crm.product.view",
    "crm.product.manage",
    "crm.customer.edit",
    "crm.lead.edit",
    "crm.schema.manage",
)
_EDIT = require_any_permission(
    "crm.customer.edit",
    "crm.lead.edit",
    "crm.deal.edit",
    "crm.quote.edit",
    "crm.contract.edit",
    "crm.payment.edit",
    "crm.payment.create",
    "crm.product.manage",
)
_MANAGE = require_any_permission(
    "crm.schema.manage",
    "crm.pipeline.manage",
    "crm.customer.edit",
    "crm.lead.edit",
)


@router.get("/tags", response_model=list[TagOut])
def api_list_tags(
    ctx: TenantContext = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    return tag_service.list_tags(db, ctx.tenant_id)


@router.post("/tags", response_model=TagOut, status_code=201)
def api_create_tag(
    body: TagCreate,
    ctx: TenantContext = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    return tag_service.create_tag(db, ctx, name=body.name, color=body.color, category=body.category)


@router.patch("/tags/{tag_id}", response_model=TagOut)
def api_update_tag(
    tag_id: UUID,
    body: TagUpdate,
    ctx: TenantContext = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    return tag_service.update_tag(
        db,
        ctx,
        tag_id,
        name=body.name,
        color=body.color,
        category=body.category,
    )


@router.delete("/tags/{tag_id}", status_code=204)
def api_delete_tag(
    tag_id: UUID,
    ctx: TenantContext = Depends(_MANAGE),
    db: Session = Depends(get_db),
):
    tag_service.delete_tag(db, ctx, tag_id)


@router.get("/entity-tags", response_model=list[EntityTagOut])
def api_list_entity_tags(
    entity_type: str = Query(...),
    entity_id: UUID = Query(...),
    ctx: TenantContext = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    rows = tag_service.list_entity_tags(db, ctx.tenant_id, entity_type, entity_id)
    return [
        EntityTagOut(
            id=et.id,
            entity_type=et.entity_type,
            entity_id=et.entity_id,
            tag_id=et.tag_id,
            tag_name=tag.name,
            created_at=et.created_at,
        )
        for et, tag in rows
    ]


@router.post("/entity-tags", response_model=EntityTagOut, status_code=201)
def api_bind_entity_tag(
    body: EntityTagBind,
    ctx: TenantContext = Depends(_EDIT),
    db: Session = Depends(get_db),
):
    et = tag_service.bind_tag(
        db,
        ctx,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        tag_id=body.tag_id,
        tag_name=body.tag_name,
    )
    names = tag_service.entity_tag_names(db, ctx.tenant_id, et.entity_type, et.entity_id)
    tag_name = next((n for n in names if True), None)
    # 精确拿到本次绑定名
    from app.models.crm import Tag
    from app.database import uuid_eq

    tag = db.query(Tag).filter(uuid_eq(Tag.id, et.tag_id)).first()
    return EntityTagOut(
        id=et.id,
        entity_type=et.entity_type,
        entity_id=et.entity_id,
        tag_id=et.tag_id,
        tag_name=tag.name if tag else tag_name,
        created_at=et.created_at,
    )


@router.delete("/entity-tags", status_code=204)
def api_unbind_entity_tag(
    entity_type: str = Query(...),
    entity_id: UUID = Query(...),
    tag_id: UUID = Query(...),
    ctx: TenantContext = Depends(_EDIT),
    db: Session = Depends(get_db),
):
    tag_service.unbind_tag(
        db, ctx, entity_type=entity_type, entity_id=entity_id, tag_id=tag_id
    )
