"""商家端权益。对照 PRD 01-管理端UI.html #a12 / #a12a。"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import (
    EntitlementExportRequest,
    EntitlementListResponse,
    EntitlementOut,
    ShopExportTaskOut,
)
from app.services.permission_service import require_permission
from app.services.shop import order_service

router = APIRouter(prefix="/entitlements", tags=["shop-entitlements"])

_ENT_EXPORT_PERM = require_permission(
    "shop.entitlement.list_all", forbidden_detail="无导出权限"
)


def _list_kwargs(
    *,
    status: str | None,
    q: str | None,
    product_type: str | None,
    buyer_id: UUID | None,
    shop_id: UUID | None,
    activated_from: date | None,
    activated_to: date | None,
    expires_from: date | None,
    expires_to: date | None,
) -> dict:
    return {
        "status_filter": status,
        "q": q,
        "product_type": product_type,
        "buyer_id": buyer_id,
        "shop_id": shop_id,
        "activated_from": activated_from,
        "activated_to": activated_to,
        "expires_from": expires_from,
        "expires_to": expires_to,
    }


@router.get("", response_model=EntitlementListResponse)
def list_entitlements(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    product_type: str | None = Query(default=None),
    buyer_id: UUID | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    activated_from: date | None = Query(default=None),
    activated_to: date | None = Query(default=None),
    expires_from: date | None = Query(default=None),
    expires_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ctx: TenantContext = Depends(require_permission("shop.entitlement.list_all")),
    db: Session = Depends(get_db),
):
    items, total, counts = order_service.list_entitlements_merchant(
        db,
        ctx,
        page=page,
        page_size=page_size,
        **_list_kwargs(
            status=status,
            q=q,
            product_type=product_type,
            buyer_id=buyer_id,
            shop_id=shop_id,
            activated_from=activated_from,
            activated_to=activated_to,
            expires_from=expires_from,
            expires_to=expires_to,
        ),
    )
    return EntitlementListResponse(
        items=items, total=total, page=page, page_size=page_size, status_counts=counts
    )


@router.get("/export")
def export_entitlements(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    product_type: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    activated_from: date | None = Query(default=None),
    activated_to: date | None = Query(default=None),
    expires_from: date | None = Query(default=None),
    expires_to: date | None = Query(default=None),
    ctx: TenantContext = Depends(_ENT_EXPORT_PERM),
    db: Session = Depends(get_db),
):
    csv_text = order_service.export_entitlements_csv(
        db,
        ctx,
        **_list_kwargs(
            status=status,
            q=q,
            product_type=product_type,
            buyer_id=None,
            shop_id=shop_id,
            activated_from=activated_from,
            activated_to=activated_to,
            expires_from=expires_from,
            expires_to=expires_to,
        ),
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-entitlements.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_export_task(
    body: EntitlementExportRequest | None = None,
    ctx: TenantContext = Depends(_ENT_EXPORT_PERM),
    db: Session = Depends(get_db),
):
    return order_service.create_entitlement_export_task(db, ctx, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_export_task(
    task_id: UUID,
    ctx: TenantContext = Depends(_ENT_EXPORT_PERM),
    db: Session = Depends(get_db),
):
    return order_service.get_entitlement_export_task(db, ctx, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_export_file(
    task_id: UUID,
    ctx: TenantContext = Depends(_ENT_EXPORT_PERM),
    db: Session = Depends(get_db),
):
    csv_text = order_service.read_entitlement_export_file(db, ctx, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-entitlements.csv"'},
    )


@router.get("/{entitlement_id}", response_model=EntitlementOut)
def get_entitlement(
    entitlement_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.entitlement.view")),
    db: Session = Depends(get_db),
):
    return order_service.get_entitlement_merchant(db, ctx, entitlement_id)


@router.get("/{entitlement_id}/assert-active", response_model=EntitlementOut)
def assert_active(
    entitlement_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.entitlement.view")),
    db: Session = Depends(get_db),
):
    e = order_service.assert_entitlement_active(db, entitlement_id)
    if e.tenant_id != ctx.tenant_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="权益不存在")
    return e
