"""商家端公域映射。对照 PRD 01-管理端UI.html #a14-list。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import (
    ChannelAuditListResponse,
    ChannelDemoOrderOut,
    ChannelDemoOrderRequest,
    ChannelExternalAuditRequest,
    ChannelMappingCreateRequest,
    ChannelMappingExportRequest,
    ChannelMappingListResponse,
    ChannelMappingOut,
    ChannelPreviewSyncOut,
    ChannelPreviewSyncRequest,
    ChannelResubmitRequest,
    ShopExportTaskOut,
)
from app.services.permission_service import require_permission
from app.services.shop import channel_service

router = APIRouter(prefix="/channel-mappings", tags=["shop-channels"])


def _parse_dt(v: str | None) -> datetime | None:
    if not v:
        return None
    s = v.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"invalid datetime: {v}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_dt_end(v: str | None) -> datetime | None:
    dt = _parse_dt(v)
    if dt is None:
        return None
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        return dt.replace(hour=23, minute=59, second=59)
    return dt


def _list_kwargs(
    *,
    status: str | None,
    q: str | None,
    shop_id: UUID | None,
    external_audit_status: str | None,
    path: str | None,
    mapped_from: str | None,
    mapped_to: str | None,
) -> dict:
    return {
        "status": status,
        "q": q,
        "shop_id": shop_id,
        "external_audit_status": external_audit_status,
        "path": path,
        "mapped_from": _parse_dt(mapped_from),
        "mapped_to": _parse_dt_end(mapped_to),
    }


@router.get("", response_model=ChannelMappingListResponse)
def list_mappings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    external_audit_status: str | None = Query(default=None),
    path: str | None = Query(default=None, description="A|B"),
    mapped_from: str | None = Query(default=None),
    mapped_to: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.channel.read")),
    db: Session = Depends(get_db),
):
    items, total, counts = channel_service.list_mappings(
        db,
        ctx,
        page=page,
        page_size=page_size,
        **_list_kwargs(
            status=status,
            q=q,
            shop_id=shop_id,
            external_audit_status=external_audit_status,
            path=path,
            mapped_from=mapped_from,
            mapped_to=mapped_to,
        ),
    )
    return ChannelMappingListResponse(
        items=items, total=total, page=page, page_size=page_size, status_counts=counts
    )


@router.get("/export")
def export_mappings(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    shop_id: UUID | None = Query(default=None),
    external_audit_status: str | None = Query(default=None),
    path: str | None = Query(default=None),
    mapped_from: str | None = Query(default=None),
    mapped_to: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("shop.channel.read")),
    db: Session = Depends(get_db),
):
    csv_text = channel_service.export_mappings_csv(
        db,
        ctx,
        **_list_kwargs(
            status=status,
            q=q,
            shop_id=shop_id,
            external_audit_status=external_audit_status,
            path=path,
            mapped_from=mapped_from,
            mapped_to=mapped_to,
        ),
    )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-channel-mappings.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_mapping_export_task(
    body: ChannelMappingExportRequest | None = None,
    ctx: TenantContext = Depends(require_permission("shop.channel.read")),
    db: Session = Depends(get_db),
):
    """对照 #a14-list · 04#select-common：商品映射异步导出（站内信本批不接）。"""
    body = body or ChannelMappingExportRequest()
    kwargs = _list_kwargs(
        status=body.status,
        q=body.q,
        shop_id=body.shop_id,
        external_audit_status=body.external_audit_status,
        path=body.path,
        mapped_from=body.mapped_from,
        mapped_to=body.mapped_to,
    )
    return channel_service.create_mapping_export_task(
        db, ctx, body, mapped_from=kwargs["mapped_from"], mapped_to=kwargs["mapped_to"]
    )


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_mapping_export_task(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.channel.read")),
    db: Session = Depends(get_db),
):
    return channel_service.get_mapping_export_task(db, ctx, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_mapping_export_file(
    task_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.channel.read")),
    db: Session = Depends(get_db),
):
    csv_text = channel_service.read_mapping_export_file(db, ctx, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-channel-mappings.csv"'},
    )


@router.post("", response_model=ChannelMappingOut)
def create_mapping(
    body: ChannelMappingCreateRequest,
    ctx: TenantContext = Depends(require_permission("shop.channel.map")),
    db: Session = Depends(get_db),
):
    return channel_service.create_mapping(db, ctx, body)


@router.post("/preview-sync", response_model=ChannelPreviewSyncOut)
def preview_sync(
    body: ChannelPreviewSyncRequest,
    ctx: TenantContext = Depends(require_permission("shop.channel.map")),
    db: Session = Depends(get_db),
):
    """A14-A 步2：预同步分配外部商品 ID。"""
    return channel_service.preview_sync(db, ctx, body)


@router.get("/audit", response_model=ChannelAuditListResponse)
def list_audit(
    external_order_id: str = Query(...),
    ctx: TenantContext = Depends(require_permission("shop.channel.read")),
    db: Session = Depends(get_db),
):
    items = channel_service.list_audit_by_external(
        db, external_order_id=external_order_id, tenant_id=ctx.tenant_id
    )
    return ChannelAuditListResponse(items=items, total=len(items))


@router.post("/{mapping_id}/pause", response_model=ChannelMappingOut)
def pause_mapping(
    mapping_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.channel.map")),
    db: Session = Depends(get_db),
):
    """A14：暂停同步。"""
    return channel_service.pause_mapping(db, ctx, mapping_id)


@router.post("/{mapping_id}/resume", response_model=ChannelMappingOut)
def resume_mapping(
    mapping_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.channel.map")),
    db: Session = Depends(get_db),
):
    """A14：恢复同步。"""
    return channel_service.resume_mapping(db, ctx, mapping_id)


@router.post("/{mapping_id}/sync", response_model=ChannelMappingOut)
def sync_mapping(
    mapping_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.channel.map")),
    db: Session = Depends(get_db),
):
    """A14-C：重新同步。"""
    return channel_service.resync_mapping(db, ctx, mapping_id)


@router.post("/{mapping_id}/external-audit", response_model=ChannelMappingOut)
def external_audit(
    mapping_id: UUID,
    body: ChannelExternalAuditRequest,
    ctx: TenantContext = Depends(require_permission("shop.channel.map")),
    db: Session = Depends(get_db),
):
    """Phase1 Mock：模拟抖店外部审核回调（通过/驳回）。"""
    return channel_service.apply_external_audit(
        db,
        ctx,
        mapping_id,
        result=body.result,
        reject_code=body.reject_code,
        reject_reason=body.reject_reason,
    )


@router.post("/{mapping_id}/resubmit", response_model=ChannelMappingOut)
def resubmit_mapping(
    mapping_id: UUID,
    body: ChannelResubmitRequest | None = None,
    ctx: TenantContext = Depends(require_permission("shop.channel.map")),
    db: Session = Depends(get_db),
):
    """A14-B：修改并重新提交。"""
    note = body.note if body else None
    return channel_service.resubmit_mapping(db, ctx, mapping_id, note=note)


@router.get("/{mapping_id}/logs", response_model=ChannelAuditListResponse)
def list_mapping_logs(
    mapping_id: UUID,
    category: str | None = Query(default=None, description="all|sync|external_audit|webhook|status"),
    ctx: TenantContext = Depends(require_permission("shop.channel.read")),
    db: Session = Depends(get_db),
):
    """A14-C 日志抽屉。"""
    items = channel_service.list_mapping_logs(
        db, ctx, mapping_id, category=category or "all"
    )
    return ChannelAuditListResponse(items=items, total=len(items))


@router.post("/{mapping_id}/demo-order", response_model=ChannelDemoOrderOut)
def demo_simulate_order(
    mapping_id: UUID,
    body: ChannelDemoOrderRequest | None = None,
    ctx: TenantContext = Depends(require_permission("shop.channel.map")),
    db: Session = Depends(get_db),
):
    """本地演示：模拟抖店买家付款 → 生成待领权订单与领权链接。"""
    mobile = body.buyer_mobile if body else None
    return channel_service.simulate_demo_douyin_order(db, ctx, mapping_id, buyer_mobile=mobile)


@router.delete("/{mapping_id}")
def delete_mapping(
    mapping_id: UUID,
    ctx: TenantContext = Depends(require_permission("shop.channel.map")),
    db: Session = Depends(get_db),
):
    return channel_service.delete_mapping(db, ctx, mapping_id)
