"""商家支付配置 A15。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import PaymentConfigOut, PaymentConfigUpsertRequest
from app.services.permission_service import require_permission
from app.services.shop import payment_service

router = APIRouter(prefix="/payment-config", tags=["shop-payment-config"])


@router.get("", response_model=PaymentConfigOut | None)
def get_config(
    ctx: TenantContext = Depends(require_permission("shop.store.settings.read")),
    db: Session = Depends(get_db),
):
    return payment_service.get_or_list_config(db, ctx)


@router.post("", response_model=PaymentConfigOut)
def upsert_config(
    body: PaymentConfigUpsertRequest,
    ctx: TenantContext = Depends(require_permission("shop.store.settings.write")),
    db: Session = Depends(get_db),
):
    return payment_service.upsert_config(db, ctx, body)


@router.post("/test")
def test_config(
    ctx: TenantContext = Depends(require_permission("shop.store.settings.write")),
    db: Session = Depends(get_db),
):
    return payment_service.test_config(db, ctx)
