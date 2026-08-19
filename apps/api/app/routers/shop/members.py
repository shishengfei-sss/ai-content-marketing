"""A16 成员 API。对照 #a16a · §8.7.1。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.services.permission_service import require_any_permission, require_permission
from app.services.shop import a16_roles_service as svc

router = APIRouter(prefix="/members", tags=["shop-members"])


class AssignMemberRequest(BaseModel):
    user_id: UUID
    role_code: str = Field(..., min_length=2, max_length=50)
    store_scope: str = Field(default="all")
    store_ids: list[UUID] = Field(default_factory=list)


class UpdateMemberRequest(BaseModel):
    role_code: str | None = None
    store_scope: str | None = None
    store_ids: list[UUID] | None = None


@router.get("")
def list_members(
    role_code: str | None = Query(default=None),
    ctx: TenantContext = Depends(
        require_any_permission("shop.role.manage", "team.member.view")
    ),
    db: Session = Depends(get_db),
):
    return {"items": svc.list_shop_members(db, ctx, role_code=role_code)}


@router.get("/candidates")
def list_candidates(
    ctx: TenantContext = Depends(
        require_permission("shop.role.manage", forbidden_detail="无角色管理权限")
    ),
    db: Session = Depends(get_db),
):
    return {"items": svc.list_assignable_users(db, ctx)}


@router.post("")
def assign_member(
    body: AssignMemberRequest,
    ctx: TenantContext = Depends(
        require_permission("shop.role.manage", forbidden_detail="无角色管理权限")
    ),
    db: Session = Depends(get_db),
):
    return svc.assign_member(
        db,
        ctx,
        user_id=body.user_id,
        role_code=body.role_code,
        store_scope=body.store_scope,
        store_ids=body.store_ids,
    )


@router.patch("/{user_id}")
def update_member(
    user_id: UUID,
    body: UpdateMemberRequest,
    ctx: TenantContext = Depends(
        require_permission("shop.role.manage", forbidden_detail="无角色管理权限")
    ),
    db: Session = Depends(get_db),
):
    return svc.update_member(
        db,
        ctx,
        user_id,
        role_code=body.role_code,
        store_scope=body.store_scope,
        store_ids=body.store_ids,
    )


@router.delete("/{user_id}")
def remove_member(
    user_id: UUID,
    ctx: TenantContext = Depends(
        require_permission("shop.role.manage", forbidden_detail="无角色管理权限")
    ),
    db: Session = Depends(get_db),
):
    return svc.remove_member(db, ctx, user_id)
