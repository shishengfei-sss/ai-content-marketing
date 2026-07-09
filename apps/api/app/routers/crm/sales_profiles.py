"""成员销售档案 API。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.crm import SalesProfileOut, SalesProfileUpdate
from app.services.crm.sales_org_service import list_sales_profiles, upsert_sales_profile
from app.services.permission_service import require_permission

router = APIRouter(prefix="/sales-profiles", tags=["crm-sales-profiles"])


@router.get("", response_model=list[SalesProfileOut])
def get_sales_profiles(
    ctx: TenantContext = Depends(require_permission("crm.org.manage")),
    db: Session = Depends(get_db),
):
    rows = list_sales_profiles(db, ctx.tenant_id)
    return [SalesProfileOut.model_validate(r) for r in rows]


@router.patch("/{membership_id}", response_model=SalesProfileOut)
def patch_sales_profile(
    membership_id: UUID,
    body: SalesProfileUpdate,
    ctx: TenantContext = Depends(require_permission("crm.org.manage")),
    db: Session = Depends(get_db),
):
    profile = upsert_sales_profile(db, ctx, membership_id, body)
    rows = list_sales_profiles(db, ctx.tenant_id)
    row = next((r for r in rows if str(r["membership_id"]) == str(membership_id)), None)
    if not row:
        row = {
            "membership_id": profile.membership_id,
            "user_id": ctx.user.id,
            "display_name": ctx.user.display_name,
            "phone": ctx.user.phone,
            "role_name": None,
            "primary_territory_id": profile.primary_territory_id,
            "reports_to_membership_id": profile.reports_to_membership_id,
        }
    return SalesProfileOut.model_validate(row)
