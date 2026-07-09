"""当前用户偏好 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext, get_tenant_context
from app.schemas.crm_schema import ListColumnOut, ViewPreferenceOut, ViewPreferenceUpdate
from app.services.crm.schema_service import (
    ensure_entity_schema,
    get_view_preference,
    list_active_fields,
    list_column_out,
    resolve_list_columns,
    save_view_preference,
)

router = APIRouter(prefix="/me", tags=["me"])


def _enrich_columns(db, tenant_id, entity_type: str, columns: list[dict]) -> list[ListColumnOut]:
    fields = list_active_fields(db, tenant_id, entity_type)
    field_map = {f.field_key: f for f in fields}
    out: list[ListColumnOut] = []
    for i, col in enumerate(columns):
        key = col.get("field_key")
        f = field_map.get(key)
        if not f:
            continue
        out.append(
            ListColumnOut(
                **list_column_out(
                    entity_type,
                    f,
                    visible=col.get("visible", True),
                    width=col.get("width") or f.list_width,
                    order=col.get("order", i),
                )
            )
        )
    return out


@router.get("/view-preferences/{entity_type}", response_model=ViewPreferenceOut)
def get_view_preferences(
    entity_type: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    ensure_entity_schema(db, ctx.tenant_id, entity_type)
    pref = get_view_preference(db, ctx.tenant_id, ctx.user.id, entity_type)
    if pref and pref.columns:
        return ViewPreferenceOut(
            entity_type=entity_type,
            columns=_enrich_columns(db, ctx.tenant_id, entity_type, pref.columns),
            updated_at=pref.updated_at,
        )
    defaults = resolve_list_columns(db, ctx.tenant_id, ctx.user.id, entity_type)
    return ViewPreferenceOut(
        entity_type=entity_type,
        columns=[ListColumnOut(**c) for c in defaults],
    )


@router.put("/view-preferences/{entity_type}", response_model=ViewPreferenceOut)
def put_view_preferences(
    entity_type: str,
    body: ViewPreferenceUpdate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    pref = save_view_preference(
        db,
        ctx.tenant_id,
        ctx.user.id,
        entity_type,
        [c.model_dump() for c in body.columns],
    )
    return ViewPreferenceOut(
        entity_type=entity_type,
        columns=_enrich_columns(db, ctx.tenant_id, entity_type, pref.columns),
        updated_at=pref.updated_at,
    )
