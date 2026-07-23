"""销售地区 API。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext, get_tenant_context
from app.schemas.crm import TerritoryCreate, TerritoryOut, TerritoryUpdate
from app.services.crm.sales_org_service import (
    create_territory,
    delete_territory,
    ensure_default_territories,
    get_territory,
    update_territory,
)
from app.services.permission_service import require_permission

router = APIRouter(prefix="/territories", tags=["crm-territories"])


@router.get("", response_model=list[TerritoryOut])
def get_territories(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """归属地区下拉为引用数据：租户内已登录成员可读；增删改仍需 crm.org.manage。"""
    rows = ensure_default_territories(db, ctx.tenant_id)
    return [TerritoryOut.model_validate(t) for t in rows]


@router.post("", response_model=TerritoryOut, status_code=201)
def post_territory(
    body: TerritoryCreate,
    ctx: TenantContext = Depends(require_permission("crm.org.manage")),
    db: Session = Depends(get_db),
):
    territory = create_territory(db, ctx, body)
    return TerritoryOut.model_validate(territory)


@router.patch("/{territory_id}", response_model=TerritoryOut)
def patch_territory(
    territory_id: UUID,
    body: TerritoryUpdate,
    ctx: TenantContext = Depends(require_permission("crm.org.manage")),
    db: Session = Depends(get_db),
):
    territory = get_territory(db, ctx.tenant_id, territory_id)
    if not territory:
        raise HTTPException(status_code=404, detail="地区不存在")
    territory = update_territory(db, ctx, territory, body)
    return TerritoryOut.model_validate(territory)


@router.delete("/{territory_id}", status_code=204)
def remove_territory(
    territory_id: UUID,
    ctx: TenantContext = Depends(require_permission("crm.org.manage")),
    db: Session = Depends(get_db),
):
    territory = get_territory(db, ctx.tenant_id, territory_id)
    if not territory:
        raise HTTPException(status_code=404, detail="地区不存在")
    delete_territory(db, territory)
