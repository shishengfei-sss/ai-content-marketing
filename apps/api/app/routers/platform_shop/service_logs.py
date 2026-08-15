"""商家服务记录 API（P02-B）。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.shop_platform import MerchantServiceLogItem, RenewalRequestCreate, ServiceNoteCreate
from app.services.permission_service import require_platform_shop_any, require_platform_shop_permission
from app.services.shop.service_log_service import (
    cancel_renewal_request,
    create_renewal_request,
    create_service_note,
    list_service_logs,
    mark_renewal_processing,
    revert_renewal_pending,
)

router = APIRouter(prefix="/merchants", tags=["platform-shop-service-logs"])


@router.get("/{tenant_id}/service-logs")
def get_service_logs(
    tenant_id: UUID,
    type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.merchant.read",
            "platform.shop.merchant.list_all",
            "platform.shop.merchant.list_assigned",
        )
    ),
    db: Session = Depends(get_db),
):
    return list_service_logs(
        db,
        user,
        tenant_id,
        type_filter=type,
        status_filter=status,
        q=q,
        page=page,
        page_size=page_size,
    )


@router.post("/{tenant_id}/service-logs/notes", response_model=MerchantServiceLogItem, status_code=201)
def add_service_note(
    tenant_id: UUID,
    payload: ServiceNoteCreate,
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.merchant.read",
            "platform.shop.merchant.list_all",
            "platform.shop.merchant.list_assigned",
        )
    ),
    db: Session = Depends(get_db),
):
    return create_service_note(db, user, tenant_id, payload)


@router.post("/{tenant_id}/service-logs/renewal-requests", response_model=MerchantServiceLogItem, status_code=201)
def submit_renewal_request(
    tenant_id: UUID,
    payload: RenewalRequestCreate,
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.merchant.read",
            "platform.shop.merchant.list_all",
            "platform.shop.merchant.list_assigned",
        )
    ),
    db: Session = Depends(get_db),
):
    return create_renewal_request(db, user, tenant_id, payload)


@router.post("/{tenant_id}/service-logs/renewal-requests/{service_log_id}/cancel", response_model=MerchantServiceLogItem)
def cancel_renewal(
    tenant_id: UUID,
    service_log_id: UUID,
    note: str | None = Query(default=None),
    user: User = Depends(require_platform_shop_permission("platform.shop.subscription.manage")),
    db: Session = Depends(get_db),
):
    return cancel_renewal_request(db, user, tenant_id, service_log_id, note=note)


@router.post(
    "/{tenant_id}/service-logs/renewal-requests/{service_log_id}/mark-processing",
    response_model=MerchantServiceLogItem,
)
def mark_renewal_as_processing(
    tenant_id: UUID,
    service_log_id: UUID,
    user: User = Depends(require_platform_shop_permission("platform.shop.subscription.manage")),
    db: Session = Depends(get_db),
):
    return mark_renewal_processing(db, user, tenant_id, service_log_id)


@router.post(
    "/{tenant_id}/service-logs/renewal-requests/{service_log_id}/revert-pending",
    response_model=MerchantServiceLogItem,
)
def revert_renewal_to_pending(
    tenant_id: UUID,
    service_log_id: UUID,
    user: User = Depends(require_platform_shop_permission("platform.shop.subscription.manage")),
    db: Session = Depends(get_db),
):
    return revert_renewal_pending(db, user, tenant_id, service_log_id)
