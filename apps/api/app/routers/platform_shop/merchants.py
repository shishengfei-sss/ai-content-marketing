"""平台商家管理 API（P02 / P11）。对照 PRD：06-平台端UI.html#p02-list。"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_platform_admin
from app.models import User
from app.schemas.shop_platform import (
    MerchantAssignRequest,
    MerchantBatchAssignRequest,
    MerchantBatchAssignResponse,
    MerchantCloseRequest,
    MerchantExportRequest,
    MerchantResumeRequest,
    MerchantRevealRequest,
    MerchantRevealResponse,
    MerchantSuspendRequest,
    MerchantTagsPutRequest,
    MerchantTagsPutResponse,
    PlatformMerchantDetailResponse,
    PlatformMerchantListResponse,
    PlatformPendingRenewalListResponse,
    ShopCsUserListResponse,
    ShopExportTaskOut,
    ShopMerchantTagListResponse,
)
from app.services.permission_service import require_platform_shop_any, require_platform_shop_permission
from app.services.shop.merchant_service import (
    create_merchant_export_task,
    export_platform_merchants_csv,
    get_merchant_export_task,
    get_platform_merchant_detail,
    list_pending_renewals,
    list_platform_merchants,
    read_merchant_export_file,
    reveal_merchant_sensitive,
)
from app.services.shop import merchant_assign_service, merchant_status_service

router = APIRouter(prefix="/merchants", tags=["platform-shop-merchants"])


def _parse_tag_ids(raw: str | None) -> list[UUID] | None:
    if not raw:
        return None
    out: list[UUID] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(UUID(part))
    return out or None


def _list_kwargs(
    q,
    onboarding_status,
    plan_status,
    entity_type,
    plan_label,
    fee_tier,
    account_manager_user_id,
    tag_ids,
    benefits_from,
    benefits_until,
    store_count_min,
    store_count_max,
    created_from,
    created_until,
    tab,
    include_not_onboarded,
    sort_by,
    sort_dir,
    page,
    page_size,
):
    return dict(
        q=q,
        onboarding_status=onboarding_status,
        plan_status=plan_status,
        entity_type=entity_type,
        plan_label=plan_label,
        fee_tier=fee_tier,
        account_manager_user_id=account_manager_user_id,
        tag_ids=tag_ids,
        benefits_from=benefits_from,
        benefits_until=benefits_until,
        store_count_min=store_count_min,
        store_count_max=store_count_max,
        created_from=created_from,
        created_until=created_until,
        tab=tab,
        include_not_onboarded=include_not_onboarded,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.get("", response_model=PlatformMerchantListResponse)
def list_merchants(
    q: str | None = Query(default=None, description="商家名 / 商家编码 / 租户名"),
    onboarding_status: str | None = Query(default=None),
    plan_status: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    plan_label: str | None = Query(default=None),
    fee_tier: str | None = Query(default=None),
    account_manager_user_id: UUID | None = Query(default=None),
    tag_ids: str | None = Query(default=None, description="逗号分隔的标签 UUID"),
    benefits_from: date | None = Query(default=None),
    benefits_until: date | None = Query(default=None),
    store_count_min: int | None = Query(default=None, ge=0),
    store_count_max: int | None = Query(default=None, ge=0),
    created_from: date | None = Query(default=None),
    created_until: date | None = Query(default=None),
    tab: str | None = Query(default=None),
    include_not_onboarded: bool = Query(default=False),
    sort_by: str | None = Query(
        default="created_at",
        description="display_name|merchant_code|benefits_until|store_count|created_at",
    ),
    sort_dir: str | None = Query(default="desc", description="asc|desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.merchant.read",
            "platform.shop.merchant.list_all",
            "platform.shop.merchant.list_assigned",
        )
    ),
    db: Session = Depends(get_db),
):
    return list_platform_merchants(
        db,
        user,
        **_list_kwargs(
            q,
            onboarding_status,
            plan_status,
            entity_type,
            plan_label,
            fee_tier,
            account_manager_user_id,
            _parse_tag_ids(tag_ids),
            benefits_from,
            benefits_until,
            store_count_min,
            store_count_max,
            created_from,
            created_until,
            tab,
            include_not_onboarded,
            sort_by,
            sort_dir,
            page,
            page_size,
        ),
    )


@router.get("/export")
def export_merchants(
    q: str | None = Query(default=None),
    onboarding_status: str | None = Query(default=None),
    plan_status: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    plan_label: str | None = Query(default=None),
    fee_tier: str | None = Query(default=None),
    account_manager_user_id: UUID | None = Query(default=None),
    tag_ids: str | None = Query(default=None),
    benefits_from: date | None = Query(default=None),
    benefits_until: date | None = Query(default=None),
    store_count_min: int | None = Query(default=None, ge=0),
    store_count_max: int | None = Query(default=None, ge=0),
    created_from: date | None = Query(default=None),
    created_until: date | None = Query(default=None),
    tab: str | None = Query(default=None),
    include_not_onboarded: bool = Query(default=True),
    sort_by: str | None = Query(default="created_at"),
    sort_dir: str | None = Query(default="desc"),
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.merchant.read",
            "platform.shop.merchant.list_all",
            "platform.shop.merchant.list_assigned",
        )
    ),
    db: Session = Depends(get_db),
):
    """按当前筛选导出 CSV（最多 2000 行）。"""
    csv_text = export_platform_merchants_csv(
        db,
        user,
        q=q,
        onboarding_status=onboarding_status,
        plan_status=plan_status,
        entity_type=entity_type,
        plan_label=plan_label,
        fee_tier=fee_tier,
        account_manager_user_id=account_manager_user_id,
        tag_ids=_parse_tag_ids(tag_ids),
        benefits_from=benefits_from,
        benefits_until=benefits_until,
        store_count_min=store_count_min,
        store_count_max=store_count_max,
        created_from=created_from,
        created_until=created_until,
        tab=tab,
        include_not_onboarded=include_not_onboarded,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=2000,
        raise_too_many=False,
    )
    payload = "\ufeff" + csv_text
    return StreamingResponse(
        iter([payload.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-merchants.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_export_task(
    body: MerchantExportRequest | None = None,
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.merchant.read",
            "platform.shop.merchant.list_all",
            "platform.shop.merchant.list_assigned",
        )
    ),
    db: Session = Depends(get_db),
):
    """对照 #p02-list-select-spec：异步导出任务（站内信本批不接，页内下载）。"""
    return create_merchant_export_task(db, user, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_export_task(
    task_id: UUID,
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.merchant.read",
            "platform.shop.merchant.list_all",
            "platform.shop.merchant.list_assigned",
        )
    ),
    db: Session = Depends(get_db),
):
    return get_merchant_export_task(db, user, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_export_file(
    task_id: UUID,
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.merchant.read",
            "platform.shop.merchant.list_all",
            "platform.shop.merchant.list_assigned",
        )
    ),
    db: Session = Depends(get_db),
):
    csv_text = read_merchant_export_file(db, user, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-merchants.csv"'},
    )


@router.get("/pending-renewals", response_model=PlatformPendingRenewalListResponse)
def list_pending_renewal_requests(
    _: User = Depends(require_platform_shop_permission("platform.shop.subscription.manage")),
    db: Session = Depends(get_db),
):
    return list_pending_renewals(db)


@router.post("/{tenant_id}/suspend", response_model=PlatformMerchantDetailResponse)
def suspend_merchant(
    tenant_id: UUID,
    body: MerchantSuspendRequest,
    user: User = Depends(require_platform_shop_permission("platform.shop.merchant.manage")),
    db: Session = Depends(get_db),
):
    return merchant_status_service.suspend_merchant(db, user, tenant_id, body)


@router.post("/{tenant_id}/resume", response_model=PlatformMerchantDetailResponse)
def resume_merchant(
    tenant_id: UUID,
    body: MerchantResumeRequest | None = None,
    user: User = Depends(require_platform_shop_permission("platform.shop.merchant.manage")),
    db: Session = Depends(get_db),
):
    return merchant_status_service.resume_merchant(db, user, tenant_id, body)


@router.post("/{tenant_id}/close", response_model=PlatformMerchantDetailResponse)
def close_merchant(
    tenant_id: UUID,
    body: MerchantCloseRequest,
    user: User = Depends(require_platform_shop_permission("platform.shop.merchant.manage")),
    db: Session = Depends(get_db),
):
    return merchant_status_service.close_merchant(db, user, tenant_id, body)


@router.get("/{tenant_id}", response_model=PlatformMerchantDetailResponse)
def get_merchant_detail(
    tenant_id: UUID,
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.merchant.read",
            "platform.shop.merchant.list_all",
            "platform.shop.merchant.list_assigned",
        )
    ),
    db: Session = Depends(get_db),
):
    return get_platform_merchant_detail(db, user, tenant_id)


@router.post("/{tenant_id}/reveal-sensitive", response_model=MerchantRevealResponse)
def reveal_sensitive(
    tenant_id: UUID,
    body: MerchantRevealRequest | None = None,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """对照 #p02b-materials：揭露经营联系人手机 / 身份证号。"""
    field = body.field if body is not None else "contact_mobile"
    return reveal_merchant_sensitive(db, user, tenant_id, field)


@router.post("/{tenant_id}/assign", response_model=PlatformMerchantDetailResponse)
def assign_merchant_manager(
    tenant_id: UUID,
    body: MerchantAssignRequest,
    user: User = Depends(require_platform_shop_permission("platform.shop.merchant.assign")),
    db: Session = Depends(get_db),
):
    return merchant_assign_service.assign_account_manager(db, user, tenant_id, body)


@router.put("/{tenant_id}/tags", response_model=MerchantTagsPutResponse)
def put_merchant_tags(
    tenant_id: UUID,
    body: MerchantTagsPutRequest,
    user: User = Depends(require_platform_shop_permission("platform.shop.merchant.tag")),
    db: Session = Depends(get_db),
):
    return merchant_assign_service.put_merchant_tags(db, user, tenant_id, body)


catalog_router = APIRouter(tags=["platform-shop-merchants"])


@catalog_router.post("/merchants/batch-assign", response_model=MerchantBatchAssignResponse)
def batch_assign_merchant_managers(
    body: MerchantBatchAssignRequest,
    user: User = Depends(require_platform_shop_permission("platform.shop.merchant.assign")),
    db: Session = Depends(get_db),
):
    """对照 #p02e 批量分配管家：单次 ≤50，含不可分配则整批失败。"""
    return merchant_assign_service.batch_assign_account_managers(db, user, body)


@catalog_router.get("/cs-users", response_model=ShopCsUserListResponse)
def list_shop_cs_users(
    _: User = Depends(require_platform_shop_permission("platform.shop.merchant.assign")),
    db: Session = Depends(get_db),
):
    return merchant_assign_service.list_cs_users(db)


@catalog_router.get("/merchant-tags", response_model=ShopMerchantTagListResponse)
def list_shop_merchant_tags(
    q: str | None = Query(default=None),
    _: User = Depends(
        require_platform_shop_any(
            "platform.shop.merchant.read",
            "platform.shop.merchant.list_all",
            "platform.shop.merchant.list_assigned",
            "platform.shop.merchant.tag",
        )
    ),
    db: Session = Depends(get_db),
):
    return merchant_assign_service.list_merchant_tags(db, q=q)
