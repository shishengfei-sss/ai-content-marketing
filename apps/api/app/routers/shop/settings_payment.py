"""A15 支付与进件 API。对照 #a15 · POST /shop/settings/payment/*。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.services.permission_service import require_permission
from app.services.shop import a15_payment_onboarding_service as svc

router = APIRouter(prefix="/settings/payment", tags=["shop-settings-payment"])


class OnboardingSubmitRequest(BaseModel):
    settlement_bank: str = Field(..., min_length=1, max_length=100)
    settlement_account: str = Field(..., min_length=8, max_length=32)
    settlement_account_name: str = Field(..., min_length=2, max_length=200)
    remark: str | None = Field(default=None, max_length=500)


@router.get("")
def get_payment(
    ctx: TenantContext = Depends(require_permission("shop.settings.read")),
    db: Session = Depends(get_db),
):
    return svc.get_payment_settings(db, ctx, can_write=True)


@router.post("/onboarding")
def submit_onboarding(
    body: OnboardingSubmitRequest,
    ctx: TenantContext = Depends(require_permission("shop.settings.write")),
    db: Session = Depends(get_db),
):
    return svc.submit_onboarding(
        db,
        ctx,
        settlement_bank=body.settlement_bank,
        settlement_account=body.settlement_account,
        settlement_account_name=body.settlement_account_name,
        remark=body.remark,
    )


@router.post("/test")
def test_payment(
    ctx: TenantContext = Depends(require_permission("shop.settings.write")),
    db: Session = Depends(get_db),
):
    return svc.test_payment(db, ctx)
