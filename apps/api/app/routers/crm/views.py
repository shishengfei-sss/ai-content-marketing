"""CRM 列表视图 API。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext, get_tenant_context
from app.schemas.crm_views import ListViewCreate, ListViewOut, ListViewUpdate
from app.services.crm.view_service import (
    create_view,
    delete_view,
    get_view,
    list_visible_views,
    update_view,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/views", tags=["crm-views"])


@router.get("", response_model=list[ListViewOut])
def get_views(
    entity_type: str | None = Query(default=None),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    views = list_visible_views(db, ctx, entity_type)
    return [ListViewOut.model_validate(v) for v in views]


@router.post("", response_model=ListViewOut, status_code=201)
def post_view(
    body: ListViewCreate,
    ctx: TenantContext = Depends(require_permission("crm.view.save_own")),
    db: Session = Depends(get_db),
):
    view = create_view(db, ctx, body)
    return ListViewOut.model_validate(view)


@router.patch("/{view_id}", response_model=ListViewOut)
def patch_view(
    view_id: UUID,
    body: ListViewUpdate,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    view = get_view(db, ctx.tenant_id, view_id)
    if not view:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="视图不存在")
    view = update_view(db, ctx, view, body)
    return ListViewOut.model_validate(view)


@router.delete("/{view_id}", status_code=204)
def remove_view(
    view_id: UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    view = get_view(db, ctx.tenant_id, view_id)
    if not view:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="视图不存在")
    delete_view(db, ctx, view)
