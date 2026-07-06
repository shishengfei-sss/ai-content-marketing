from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas import TenantProfileOut, TenantProfileUpdate
from app.services.permission_service import require_permission
from app.services.tenant_service import get_tenant_profile, update_tenant_profile

router = APIRouter(prefix="/tenant", tags=["tenant"])


@router.get("/profile", response_model=TenantProfileOut)
def get_profile(ctx: TenantContext = Depends(require_permission("tenant.manage")), db: Session = Depends(get_db)):
    return get_tenant_profile(db, ctx.tenant_id)


@router.patch("/profile", response_model=TenantProfileOut)
def patch_profile(
    body: TenantProfileUpdate,
    ctx: TenantContext = Depends(require_permission("tenant.manage")),
    db: Session = Depends(get_db),
):
    return update_tenant_profile(
        db,
        ctx.tenant_id,
        name=body.name,
        industry_code=body.industry_code,
        credit_code=body.credit_code,
    )
