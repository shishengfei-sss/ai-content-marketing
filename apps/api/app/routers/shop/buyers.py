"""商家端买家。对照 PRD 01-管理端UI.html #a11 / #a11a。"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import (
    BuyerExportRequest,
    BuyerLearningListResponse,
    MerchantBuyerDetailOut,
    MerchantBuyerListResponse,
    ShopExportTaskOut,
)
from app.services.permission_service import require_permission
from app.services.shop import merchant_buyer_service

router = APIRouter(prefix="/buyers", tags=["shop-buyers"])

_BUYER_EXPORT_PERM = require_permission(
    "shop.buyer.list_all", forbidden_detail="无导出权限"
)


def _list_kwargs(
    *,
    q: str | None,
    tab: str | None,
    shop_id: UUID | None,
    account_status: str | None,
    order_count_min: int | None,
    entitlement_count_min: int | None,
    registered_from: date | None,
    registered_to: date | None,
    last_order_from: date | None,
    last_order_to: date | None,
) -> dict:
    return {
        "q": q,
        "tab": tab,
        "shop_id": shop_id,
        "account_status": account_status,
        "order_count_min": order_count_min,
        "entitlement_count_min": entitlement_count_min,
        "registered_from": registered_from,
        "registered_to": registered_to,
        "last_order_from": last_order_from,
        "last_order_to": last_order_to,
    }


@router.get("", response_model=MerchantBuyerListResponse)
def list_buyers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    tab: str | None = Query(default=None, description="all|with_entitlement|new_7d|blocked"),
    shop_id: UUID | None = Query(default=None),
    account_status: str | None = Query(default=None, description="active|blocked"),
    order_count_min: int | None = Query(default=None, ge=0),
    entitlement_count_min: int | None = Query(default=None, ge=0),
    registered_from: date | None = Query(default=None),
    registered_to: date | None = Query(default=None),
    last_order_from: date | None = Query(default=None),
    last_order_to: date | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.buyer.list_all")),
    db: Session = Depends(get_db),
):
    items, total, counts = merchant_buyer_service.list_buyers(
        db,
        ctx,
        page=page,
        page_size=page_size,
        **_list_kwargs(
            q=q,
            tab=tab,
            shop_id=shop_id,
            account_status=account_status,
            order_count_min=order_count_min,
            entitlement_count_min=entitlement_count_min,
            registered_from=registered_from,
            registered_to=registered_to,
            last_order_from=last_order_from,
            last_order_to=last_order_to,
        ),
    )
    return MerchantBuyerListResponse(
        items=items, total=total, page=page, page_size=page_size, status_counts=counts
    )


@router.get("/export")
def export_buyers(
    q: str | None = Query(default=None),
    tab: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    account_status: str | None = Query(default=None),
    order_count_min: int | None = Query(default=None, ge=0),
    entitlement_count_min: int | None = Query(default=None, ge=0),
    registered_from: date | None = Query(default=None),
    registered_to: date | None = Query(default=None),
    last_order_from: date | None = Query(default=None),
    last_order_to: date | None = Query(default=None),
    ctx: TenantContext = Depends(_BUYER_EXPORT_PERM),
    db: Session = Depends(get_db),
):
    csv_text = merchant_buyer_service.export_buyers_csv(
        db,
        ctx,
        **_list_kwargs(
            q=q,
            tab=tab,
            shop_id=shop_id,
            account_status=account_status,
            order_count_min=order_count_min,
            entitlement_count_min=entitlement_count_min,
            registered_from=registered_from,
            registered_to=registered_to,
            last_order_from=last_order_from,
            last_order_to=last_order_to,
        ),
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-buyers.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_export_task(
    body: BuyerExportRequest | None = None,
    ctx: TenantContext = Depends(_BUYER_EXPORT_PERM),
    db: Session = Depends(get_db),
):
    return merchant_buyer_service.create_buyer_export_task(db, ctx, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_export_task(
    task_id: UUID,
    ctx: TenantContext = Depends(_BUYER_EXPORT_PERM),
    db: Session = Depends(get_db),
):
    return merchant_buyer_service.get_buyer_export_task(db, ctx, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_export_file(
    task_id: UUID,
    ctx: TenantContext = Depends(_BUYER_EXPORT_PERM),
    db: Session = Depends(get_db),
):
    csv_text = merchant_buyer_service.read_buyer_export_file(db, ctx, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-buyers.csv"'},
    )


@router.get("/{buyer_id}", response_model=MerchantBuyerDetailOut)
def get_buyer(
    buyer_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.buyer.view")),
    db: Session = Depends(get_db),
):
    return merchant_buyer_service.get_buyer(db, ctx, buyer_id)


@router.post("/{buyer_id}/reveal-sensitive", response_model=MerchantBuyerDetailOut)
def reveal_sensitive(
    buyer_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.buyer.view")),
    db: Session = Depends(get_db),
):
    return merchant_buyer_service.reveal_buyer_mobile(db, ctx, buyer_id)


@router.get("/{buyer_id}/learning-progress", response_model=BuyerLearningListResponse)
def learning_progress(
    buyer_id: UUID,
    shop_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.buyer.view")),
    db: Session = Depends(get_db),
):
    return merchant_buyer_service.list_learning_progress(db, ctx, buyer_id, shop_id=shop_id)
