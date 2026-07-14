"""通用实体团队成员 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import EntityTeamMemberAdd, EntityTeamMemberOut
from app.services.crm import entity_team_service
from app.services.permission_service import require_any_permission

router = APIRouter(prefix="/team-members", tags=["crm-team-members"])

_VIEW = require_any_permission("crm.deal.view", "crm.customer.view", "crm.lead.view", "crm.deal.edit")
_EDIT = require_any_permission("crm.deal.edit", "crm.customer.edit", "crm.lead.edit")


@router.get("", response_model=list[EntityTeamMemberOut])
def api_list(
    entity_type: str = Query(...),
    entity_id: UUID = Query(...),
    ctx: TenantContext = Depends(_VIEW),
    db: Session = Depends(get_db),
):
    return entity_team_service.list_members(db, ctx.tenant_id, entity_type, entity_id)


@router.post("", response_model=EntityTeamMemberOut, status_code=201)
def api_add(
    body: EntityTeamMemberAdd,
    ctx: TenantContext = Depends(_EDIT),
    db: Session = Depends(get_db),
):
    return entity_team_service.add_member(
        db,
        ctx,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        user_id=body.user_id,
        role=body.role,
    )


@router.delete("/{member_id}", status_code=204)
def api_remove(
    member_id: UUID,
    ctx: TenantContext = Depends(_EDIT),
    db: Session = Depends(get_db),
):
    entity_team_service.remove_member(db, ctx, member_id)
