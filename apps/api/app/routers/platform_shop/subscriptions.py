"""P11 订阅开通 API。对照 PRD：06#p11 · §8.3。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.shop_platform import (
    ShopExportTaskOut,
    SubscriptionCancelRequest,
    SubscriptionCreateRequest,
    SubscriptionExportRequest,
    SubscriptionListResponse,
    SubscriptionOut,
    SubscriptionRenewRequest,
    SubscriptionReplaceRequest,
)
from app.services.permission_service import require_platform_shop_any, require_platform_shop_permission
from app.services.shop import subscription_service

router = APIRouter(tags=["platform-shop-subscriptions"])

_sub_read = require_platform_shop_any(
    "platform.shop.subscription.read",
    "platform.shop.subscription.manage",
)
_sub_manage = require_platform_shop_permission("platform.shop.subscription.manage")


@router.get("/subscriptions", response_model=SubscriptionListResponse)
def list_subscriptions(
    tenant_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    plan_code: str | None = Query(default=None),
    q: str | None = Query(default=None),
    view: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str | None = Query(default=None),
    sort_dir: str = Query(default="desc"),
    db: Session = Depends(get_db),
    user: User = Depends(_sub_read),
):
    items, total = subscription_service.list_subscriptions(
        db,
        user,
        tenant_id=tenant_id,
        status_filter=status,
        plan_code=plan_code,
        q=q,
        view=view,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return SubscriptionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/subscriptions/export")
def export_subscriptions(
    tenant_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    plan_code: str | None = Query(default=None),
    q: str | None = Query(default=None),
    view: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(_sub_read),
):
    csv_text = subscription_service.export_list_csv(
        db,
        user,
        tenant_id=tenant_id,
        status_filter=status,
        plan_code=plan_code,
        q=q,
        view=view,
    )
    payload = "\ufeff" + csv_text
    return StreamingResponse(
        iter([payload.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-subscriptions.csv"'},
    )


@router.post("/subscriptions/export", response_model=ShopExportTaskOut)
def create_subscriptions_export_task(
    body: SubscriptionExportRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(_sub_read),
):
    """对照 #p11 · 04#select-common：列表异步导出（站内信本批不接，页内下载）。"""
    return subscription_service.create_subscription_export_task(db, user, body)


@router.get("/subscriptions/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_subscriptions_export_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(_sub_read),
):
    return subscription_service.get_subscription_export_task(db, user, task_id)


@router.get("/subscriptions/export-tasks/{task_id}/file")
def download_subscriptions_export_file(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(_sub_read),
):
    csv_text = subscription_service.read_subscription_export_file(db, user, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-subscriptions.csv"'},
    )


@router.post("/subscriptions", response_model=SubscriptionOut)
def create_subscription(
    body: SubscriptionCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_sub_manage),
):
    return subscription_service.create_subscription(db, user, body)


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
def get_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(_sub_read),
):
    return subscription_service.get_subscription(db, user, subscription_id)


@router.post("/subscriptions/{subscription_id}/replace", response_model=SubscriptionOut)
def replace_subscription(
    subscription_id: UUID,
    body: SubscriptionReplaceRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_sub_manage),
):
    return subscription_service.replace_subscription(db, user, subscription_id, body)


@router.post("/subscriptions/{subscription_id}/renew", response_model=SubscriptionOut)
def renew_subscription(
    subscription_id: UUID,
    body: SubscriptionRenewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_sub_manage),
):
    return subscription_service.renew_subscription(db, user, subscription_id, body)


@router.post("/subscriptions/{subscription_id}/cancel", response_model=SubscriptionOut)
def cancel_subscription(
    subscription_id: UUID,
    body: SubscriptionCancelRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(_sub_manage),
):
    return subscription_service.cancel_subscription(db, user, subscription_id, body)


@router.get("/merchants/{tenant_id}/subscriptions")
def merchant_subscriptions(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(_sub_read),
):
    return subscription_service.merchant_subscriptions_with_entitlements(db, user, tenant_id)


@router.get("/merchants/{tenant_id}/entitlements")
def merchant_entitlements(
    tenant_id: UUID,
    preview_plan: str | None = Query(default=None),
    preview_mode: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(_sub_read),
):
    return subscription_service.merchant_entitlements(
        db, user, tenant_id, preview_plan=preview_plan, preview_mode=preview_mode
    )
