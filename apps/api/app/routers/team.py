from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas import (
    MemberCreateRequest,
    MemberOut,
    MemberRoleUpdateRequest,
    MemberUpdateRequest,
    RoleCreateRequest,
    RoleOut,
    RoleUpdateRequest,
)
from app.services.permission_service import require_permission
from app.services.team_service import (
    add_member,
    create_custom_role,
    delete_custom_role,
    disable_member,
    list_members,
    list_roles,
    update_member,
    update_member_role,
    update_role_permissions,
)

router = APIRouter(prefix="/team", tags=["team"])


def _role_out(role) -> RoleOut:
    return RoleOut(
        id=role.id,
        code=role.code,
        name=role.name,
        is_system=role.is_system,
        permissions=sorted({p.permission_code for p in role.permissions}),
    )


def _member_out(m) -> MemberOut:
    role = m.role
    return MemberOut(
        id=m.id,
        user_id=m.user_id,
        phone=m.user.phone,
        display_name=m.user.display_name,
        role_id=m.role_id,
        role_code=role.code if role else "",
        role_name=role.name if role else "",
        is_active=m.is_active,
        joined_at=m.joined_at,
    )


@router.get("/roles", response_model=list[RoleOut])
def get_roles(ctx: TenantContext = Depends(require_permission("team.role.manage")), db: Session = Depends(get_db)):
    return [_role_out(r) for r in list_roles(db, ctx.tenant_id)]


@router.post("/roles", response_model=RoleOut)
def post_role(
    body: RoleCreateRequest,
    ctx: TenantContext = Depends(require_permission("team.role.manage")),
    db: Session = Depends(get_db),
):
    role = create_custom_role(db, ctx.tenant_id, name=body.name, permissions=body.permissions)
    return _role_out(role)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def patch_role(
    role_id: UUID,
    body: RoleUpdateRequest,
    ctx: TenantContext = Depends(require_permission("team.role.manage")),
    db: Session = Depends(get_db),
):
    role = update_role_permissions(
        db,
        ctx.tenant_id,
        role_id,
        operator=ctx.membership,
        name=body.name,
        permissions=body.permissions,
    )
    return _role_out(role)


@router.delete("/roles/{role_id}")
def remove_role(
    role_id: UUID,
    ctx: TenantContext = Depends(require_permission("team.role.manage")),
    db: Session = Depends(get_db),
):
    delete_custom_role(db, ctx.tenant_id, role_id)
    return {"ok": True}


@router.get("/members", response_model=list[MemberOut])
def get_members(ctx: TenantContext = Depends(require_permission("team.member.view")), db: Session = Depends(get_db)):
    return [_member_out(m) for m in list_members(db, ctx.tenant_id)]


@router.post("/members", response_model=MemberOut)
def post_member(
    body: MemberCreateRequest,
    ctx: TenantContext = Depends(require_permission("team.member.manage")),
    db: Session = Depends(get_db),
):
    m = add_member(
        db,
        ctx.tenant_id,
        ctx.membership,
        phone=body.phone,
        display_name=body.display_name,
        password=body.password,
    )
    return _member_out(m)


@router.patch("/members/{membership_id}/role", response_model=MemberOut)
def patch_member_role(
    membership_id: UUID,
    body: MemberRoleUpdateRequest,
    ctx: TenantContext = Depends(require_permission("team.member.manage")),
    db: Session = Depends(get_db),
):
    m = update_member_role(db, ctx.tenant_id, ctx.membership, membership_id, body.role_id)
    return _member_out(m)


@router.patch("/members/{membership_id}", response_model=MemberOut)
def patch_member(
    membership_id: UUID,
    body: MemberUpdateRequest,
    ctx: TenantContext = Depends(require_permission("team.member.manage")),
    db: Session = Depends(get_db),
):
    m = update_member(
        db,
        ctx.tenant_id,
        ctx.membership,
        membership_id,
        display_name=body.display_name,
    )
    return _member_out(m)


@router.post("/members/{membership_id}/disable", response_model=MemberOut)
def post_disable_member(
    membership_id: UUID,
    ctx: TenantContext = Depends(require_permission("team.member.manage")),
    db: Session = Depends(get_db),
):
    m = disable_member(db, ctx.tenant_id, ctx.membership, membership_id)
    return _member_out(m)
