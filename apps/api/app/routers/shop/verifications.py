"""商家端核销台。对照 PRD 01-管理端UI.html #a08 / #a08-log。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import (
    ShopExportTaskOut,
    VerificationExecuteRequest,
    VerificationExportRequest,
    VerificationListResponse,
    VerificationLookupRequest,
    VerificationLookupResponse,
    VerificationOut,
)
from app.services.permission_service import require_permission
from app.services.shop import fulfillment_service

router = APIRouter(prefix="/verifications", tags=["shop-verifications"])


def _list_own(ctx: TenantContext, db: Session) -> bool:
    from app.services.membership_service import get_membership_permissions

    perms = set(get_membership_permissions(ctx.membership, db))
    return "shop.redemption.list_all" not in perms and "shop.redemption.list_own" in perms


@router.post("/lookup", response_model=VerificationLookupResponse)
def lookup(
    body: VerificationLookupRequest,
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    return fulfillment_service.lookup_verifications(db, ctx, body)


@router.post("/execute", response_model=VerificationOut)
def execute(
    body: VerificationExecuteRequest,
    ctx: TenantContext = Depends(require_permission("shop.redemption.execute")),
    db: Session = Depends(get_db),
):
    return fulfillment_service.execute_verification(db, ctx, body)


@router.get("/export")
def export_csv(
    q: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    operator_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    if _list_own(ctx, db):
        raise HTTPException(status_code=403, detail="无导出权限")
    csv = fulfillment_service.export_verifications_csv(
        db,
        ctx,
        list_own=False,
        q=q,
        shop_id=shop_id,
        created_from=created_from,
        created_to=created_to,
        operator_id=operator_id,
    )
    return PlainTextResponse(
        csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=verifications.csv"},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_export_task(
    body: VerificationExportRequest | None = None,
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    if _list_own(ctx, db):
        raise HTTPException(status_code=403, detail="无导出权限")
    return fulfillment_service.create_verification_export_task(db, ctx, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_export_task(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    if _list_own(ctx, db):
        raise HTTPException(status_code=403, detail="无导出权限")
    return fulfillment_service.get_verification_export_task(db, ctx, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_export_file(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    if _list_own(ctx, db):
        raise HTTPException(status_code=403, detail="无导出权限")
    csv = fulfillment_service.read_verification_export_file(db, ctx, task_id)
    return PlainTextResponse(
        csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=verifications.csv"},
    )


@router.get("/operators")
def list_operators(
    shop_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.redemption.list_all")),
    db: Session = Depends(get_db),
):
    return {
        "items": fulfillment_service.list_verification_operators(db, ctx, shop_id=shop_id)
    }


@router.get("", response_model=VerificationListResponse)
def list_verifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    operator_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    items, total = fulfillment_service.list_verifications(
        db,
        ctx,
        page=page,
        page_size=page_size,
        list_own=_list_own(ctx, db),
        q=q,
        created_from=created_from,
        created_to=created_to,
        shop_id=shop_id,
        operator_id=operator_id,
    )
    return VerificationListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{verification_id}", response_model=VerificationOut)
def get_one(
    verification_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.redemption.read")),
    db: Session = Depends(get_db),
):
    return fulfillment_service.get_verification(
        db, ctx, verification_id, list_own=_list_own(ctx, db)
    )
