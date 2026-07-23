"""可分配负责人候选列表。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas import MemberOut
from app.services.crm.sales_org_service import list_assignable_owner_memberships
from app.services.permission_service import require_any_permission

router = APIRouter(prefix="/assignable-owners", tags=["crm-assignable-owners"])


def _member_out(m) -> MemberOut:
    role = m.role
    user = m.user
    return MemberOut(
        id=m.id,
        user_id=m.user_id,
        phone=user.phone if user else None,
        display_name=(user.display_name if user else None) or (user.phone if user else None) or "",
        role_id=m.role_id,
        role_code=role.code if role else "",
        role_name=role.name if role else "",
        is_active=m.is_active,
        joined_at=m.joined_at,
    )


@router.get("", response_model=list[MemberOut])
def api_list_assignable_owners(
    include_user_id: UUID | None = Query(default=None, description="当前负责人，确保仍出现在下拉中"),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.lead.assign",
            "crm.customer.assign",
            "crm.deal.assign",
            "crm.order.assign",
            "crm.campaign.edit",
            "crm.campaign.manage",
            "crm.task.assign",
            "crm.task.create",
        )
    ),
    db: Session = Depends(get_db),
):
    rows = list_assignable_owner_memberships(db, ctx, include_user_id=include_user_id)
    return [_member_out(m) for m in rows]
