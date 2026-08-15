"""A15-S 短信与领权 API。对照 #a15-sms · /shop/settings/sms。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.services.permission_service import require_permission
from app.services.shop import a15_sms_settings_service as svc

router = APIRouter(prefix="/settings/sms", tags=["shop-settings-sms"])


class SmsSettingsUpdate(BaseModel):
    claim_landing_base: str = Field(..., min_length=8, max_length=500)
    claim_expire_days: int = Field(..., ge=1, le=30)


class CheckDomainRequest(BaseModel):
    claim_landing_base: str = Field(..., min_length=8, max_length=500)


class TestSmsRequest(BaseModel):
    mobile: str = Field(..., min_length=11, max_length=11)


@router.get("")
def get_sms(
    ctx: TenantContext = Depends(require_permission("shop.settings.read")),
    db: Session = Depends(get_db),
):
    return svc.get_sms_settings(db, ctx)


@router.put("")
def put_sms(
    body: SmsSettingsUpdate,
    ctx: TenantContext = Depends(require_permission("shop.settings.write")),
    db: Session = Depends(get_db),
):
    return svc.update_sms_settings(
        db,
        ctx,
        claim_landing_base=body.claim_landing_base,
        claim_expire_days=body.claim_expire_days,
    )


@router.post("/check-domain")
def check_domain(
    body: CheckDomainRequest,
    ctx: TenantContext = Depends(require_permission("shop.settings.write")),
    db: Session = Depends(get_db),
):
    return svc.check_domain(db, ctx, url=body.claim_landing_base)


@router.post("/test")
def test_sms(
    body: TestSmsRequest,
    ctx: TenantContext = Depends(require_permission("shop.settings.write")),
    db: Session = Depends(get_db),
):
    return svc.send_test_sms(db, ctx, mobile=body.mobile)
