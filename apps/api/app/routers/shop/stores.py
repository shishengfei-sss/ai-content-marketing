"""商家端店铺 A17 + A19 单店设置。对照 #a17 · #a19。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext, get_tenant_context
from app.schemas.shop_platform import ShopExportTaskOut, StoreExportRequest
from app.services.permission_service import require_any_permission, require_permission
from app.services.shop import fulfillment_service, store_manage_service, store_settings_service

router = APIRouter(prefix="/stores", tags=["shop-stores"])


class CrossRedeemRequest(BaseModel):
    allow_cross_shop_redeem: bool
    shop_id: UUID | None = None


class StoreDisplayPatch(BaseModel):
    shop_id: UUID | None = None
    name: str | None = None
    logo_url: str | None = None
    intro: str | None = None
    service_phone: str | None = None
    theme_color: str | None = None
    close_order_minutes: int | None = Field(default=None, ge=5, le=1440)
    default_category_id: UUID | None = None
    clear_default_category: bool = False


class StoreRefundPatch(BaseModel):
    shop_id: UUID | None = None
    default_refund_policy: str


class StoreCreateRequest(BaseModel):
    name: str
    slug: str
    intro: str | None = None


@router.get("")
def list_stores(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(default=None),
    tab: str | None = Query(default=None),
    status: str | None = Query(default=None),
    product_count_min: int | None = Query(default=None),
    product_count_max: int | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    sort: str | None = Query(default=None),
    include_closed: bool = Query(default=False),
    ctx: TenantContext = Depends(
        require_any_permission("shop.store.manage", "shop.store.settings.read")
    ),
    db: Session = Depends(get_db),
):
    """A17 店铺列表 + 配额。"""
    return store_manage_service.list_stores(
        db,
        ctx,
        page=page,
        page_size=page_size,
        q=q,
        tab=tab,
        status=status,
        product_count_min=product_count_min,
        product_count_max=product_count_max,
        created_from=created_from,
        created_to=created_to,
        sort=sort,
        include_closed=include_closed,
    )


@router.get("/options")
def store_options(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """A01 顶栏当前店铺。对照 #a01-select-spec。客服/运营无店铺管理权限也可拉选项。"""
    return store_manage_service.list_store_options(db, ctx)


@router.get("/export")
def export_stores(
    q: str | None = Query(default=None),
    tab: str | None = Query(default=None),
    status: str | None = Query(default=None),
    ctx: TenantContext = Depends(
        require_any_permission("shop.store.manage", "shop.store.settings.read")
    ),
    db: Session = Depends(get_db),
):
    csv_text = store_manage_service.export_stores_csv(
        db, ctx, q=q, tab=tab, status=status
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-stores.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_store_export_task(
    body: StoreExportRequest | None = None,
    ctx: TenantContext = Depends(
        require_any_permission("shop.store.manage", "shop.store.settings.read")
    ),
    db: Session = Depends(get_db),
):
    """对照 #a17 · 04#select-common：店铺列表异步导出（站内信本批不接）。"""
    return store_manage_service.create_store_export_task(db, ctx, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_store_export_task(
    task_id: UUID,
    ctx: TenantContext = Depends(
        require_any_permission("shop.store.manage", "shop.store.settings.read")
    ),
    db: Session = Depends(get_db),
):
    return store_manage_service.get_store_export_task(db, ctx, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_store_export_file(
    task_id: UUID,
    ctx: TenantContext = Depends(
        require_any_permission("shop.store.manage", "shop.store.settings.read")
    ),
    db: Session = Depends(get_db),
):
    csv_text = store_manage_service.read_store_export_file(db, ctx, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-stores.csv"'},
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_store(
    body: StoreCreateRequest,
    ctx: TenantContext = Depends(require_permission("shop.store.manage")),
    db: Session = Depends(get_db),
):
    """A17-A 新建店铺（默认草稿）。"""
    return store_manage_service.create_store(
        db, ctx, name=body.name, slug=body.slug, intro=body.intro
    )


@router.get("/settings")
def get_store_settings(
    shop_id: UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.store.settings.read")),
    db: Session = Depends(get_db),
):
    """A19：当前店（或指定 shop_id）单店设置。"""
    return store_settings_service.get_settings(db, ctx, shop_id)


@router.patch("/settings/display")
def patch_store_display(
    body: StoreDisplayPatch,
    ctx: TenantContext = Depends(require_permission("shop.store.settings.write")),
    db: Session = Depends(get_db),
):
    """A19 本店展示保存。"""
    return store_settings_service.patch_display(
        db,
        ctx,
        shop_id=body.shop_id,
        name=body.name,
        logo_url=body.logo_url,
        intro=body.intro,
        service_phone=body.service_phone,
        theme_color=body.theme_color,
        close_order_minutes=body.close_order_minutes,
        default_category_id=body.default_category_id,
        clear_default_category=body.clear_default_category,
    )


@router.patch("/settings/refund")
def patch_store_refund(
    body: StoreRefundPatch,
    ctx: TenantContext = Depends(require_permission("shop.store.settings.write")),
    db: Session = Depends(get_db),
):
    """A19 退款默认保存。"""
    return store_settings_service.patch_refund_default(
        db,
        ctx,
        shop_id=body.shop_id,
        default_refund_policy=body.default_refund_policy,
    )


@router.post("/cross-redeem")
def set_cross_redeem(
    body: CrossRedeemRequest,
    ctx: TenantContext = Depends(require_permission("shop.store.settings.write")),
    db: Session = Depends(get_db),
):
    return fulfillment_service.set_store_cross_redeem(
        db, ctx, body.allow_cross_shop_redeem, body.shop_id
    )


@router.get("/{store_id}/open-readiness")
def get_open_readiness(
    store_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.store.manage")),
    db: Session = Depends(get_db),
):
    return store_manage_service.open_readiness(db, ctx, store_id)


@router.post("/{store_id}/open")
def open_store(
    store_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.store.manage")),
    db: Session = Depends(get_db),
):
    """A17-D 开业：draft → active。"""
    return store_manage_service.open_store(db, ctx, store_id)


@router.post("/{store_id}/pause")
def pause_store(
    store_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.store.manage")),
    db: Session = Depends(get_db),
):
    """A17-B 暂停。"""
    return store_manage_service.pause_store(db, ctx, store_id)


@router.post("/{store_id}/resume")
def resume_store(
    store_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.store.manage")),
    db: Session = Depends(get_db),
):
    """A17-C 恢复营业。"""
    return store_manage_service.resume_store(db, ctx, store_id)
