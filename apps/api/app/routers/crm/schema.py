"""CRM Schema API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext, get_tenant_context
from app.models.crm import ENTITY_TYPES
from app.schemas.crm_schema import (
    CustomFieldCreate,
    EntitySchemaOut,
    FieldDefinitionOut,
    FieldDefinitionUpdate,
)
from app.services.crm.schema_service import (
    create_custom_field,
    ensure_entity_schema,
    list_active_fields,
    serialize_field_definition,
    soft_delete_field,
    update_field_definition,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/schema", tags=["crm-schema"])


@router.get("/{entity_type}", response_model=EntitySchemaOut)
def get_entity_schema(
    entity_type: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    fields = ensure_entity_schema(db, ctx.tenant_id, entity_type)
    active = [f for f in fields if f.is_active]
    return EntitySchemaOut(
        entity_type=entity_type,
        fields=[serialize_field_definition(f) for f in active],
    )


@router.get("", response_model=list[EntitySchemaOut])
def list_all_schemas(
    entity_type: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("crm.schema.manage")),
    db: Session = Depends(get_db),
):
    types = [entity_type] if entity_type else list(ENTITY_TYPES)
    out: list[EntitySchemaOut] = []
    for et in types:
        fields = ensure_entity_schema(db, ctx.tenant_id, et)
        active = [f for f in fields if f.is_active]
        out.append(
            EntitySchemaOut(
                entity_type=et,
                fields=[serialize_field_definition(f) for f in active],
            )
        )
    return out


@router.post("/{entity_type}/fields", response_model=FieldDefinitionOut, status_code=201)
def post_custom_field(
    entity_type: str,
    body: CustomFieldCreate,
    ctx: TenantContext = Depends(require_permission("crm.schema.manage")),
    db: Session = Depends(get_db),
):
    row = create_custom_field(
        db,
        ctx.tenant_id,
        entity_type,
        field_key=body.field_key,
        label=body.label,
        field_type=body.field_type,
        is_required=body.is_required,
        options=body.options,
        show_in_list_default=body.show_in_list_default,
        sort_order=body.sort_order,
        placeholder=body.placeholder,
    )
    return serialize_field_definition(row)


@router.patch("/{entity_type}/fields/{field_key}", response_model=FieldDefinitionOut)
def patch_field(
    entity_type: str,
    field_key: str,
    body: FieldDefinitionUpdate,
    ctx: TenantContext = Depends(require_permission("crm.schema.manage")),
    db: Session = Depends(get_db),
):
    row = update_field_definition(
        db,
        ctx.tenant_id,
        entity_type,
        field_key,
        label=body.label,
        is_required=body.is_required,
        options=body.options,
        show_in_list_default=body.show_in_list_default,
        sort_order=body.sort_order,
        placeholder=body.placeholder,
        list_width=body.list_width,
    )
    return serialize_field_definition(row)


@router.delete("/{entity_type}/fields/{field_key}", status_code=204)
def delete_field(
    entity_type: str,
    field_key: str,
    ctx: TenantContext = Depends(require_permission("crm.schema.manage")),
    db: Session = Depends(get_db),
):
    soft_delete_field(db, ctx.tenant_id, entity_type, field_key)
