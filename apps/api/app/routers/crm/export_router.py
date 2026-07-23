"""线索/客户导出 API。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.services.crm import export_service
from app.services.permission_service import require_any_permission

router = APIRouter(prefix="/export", tags=["crm-export"])


def _export_response(filename: str, content: bytes, media: str, row_count: int) -> Response:
    return Response(
        content=content,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Row-Count": str(row_count),
            "Access-Control-Expose-Headers": "Content-Disposition, X-Export-Row-Count",
        },
    )


@router.get("/leads")
def export_leads(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    view_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    campaign_id: UUID | None = Query(default=None),
    filters: str | None = Query(default=None, description="高级筛选 JSON"),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None, pattern="^(asc|desc)$"),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.lead.list_own",
            "crm.lead.list_team",
            "crm.lead.list_territory",
            "crm.lead.list_all",
            "crm.lead.edit",
        )
    ),
    db: Session = Depends(get_db),
):
    export_filters = {
        "view_id": view_id,
        "q": q,
        "status": status,
        "source": source,
        "owner_id": owner_id,
        "campaign_id": campaign_id,
        "filters": filters,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }
    if format == "xlsx":
        filename, content, row_count = export_service.export_xlsx(db, ctx, "lead", **export_filters)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        filename, content, row_count = export_service.export_csv(db, ctx, "lead", **export_filters)
        media = "text/csv; charset=utf-8"
    return _export_response(filename, content, media, row_count)


@router.get("/customers")
def export_customers(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    view_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    filters: str | None = Query(default=None, description="高级筛选 JSON"),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.customer.list_own",
            "crm.customer.list_team",
            "crm.customer.list_territory",
            "crm.customer.list_all",
            "crm.customer.edit",
        )
    ),
    db: Session = Depends(get_db),
):
    export_filters = {
        "view_id": view_id,
        "q": q,
        "status": status,
        "owner_id": owner_id,
        "filters": filters,
    }
    if format == "xlsx":
        filename, content, row_count = export_service.export_xlsx(db, ctx, "customer", **export_filters)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        filename, content, row_count = export_service.export_csv(db, ctx, "customer", **export_filters)
        media = "text/csv; charset=utf-8"
    return _export_response(filename, content, media, row_count)


@router.get("/orders")
def export_orders(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    view_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),
    deal_id: UUID | None = Query(default=None),
    contract_id: UUID | None = Query(default=None),
    filters: str | None = Query(default=None, description="高级筛选 JSON"),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None, pattern="^(asc|desc)$"),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.order.list_own",
            "crm.order.list_team",
            "crm.order.list_territory",
            "crm.order.list_all",
            "crm.order.edit",
        )
    ),
    db: Session = Depends(get_db),
):
    export_filters = {
        "view_id": view_id,
        "q": q,
        "status": status,
        "customer_id": customer_id,
        "deal_id": deal_id,
        "contract_id": contract_id,
        "filters": filters,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }
    if format == "xlsx":
        filename, content, row_count = export_service.export_xlsx(db, ctx, "order", **export_filters)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        filename, content, row_count = export_service.export_csv(db, ctx, "order", **export_filters)
        media = "text/csv; charset=utf-8"
    return _export_response(filename, content, media, row_count)


@router.get("/contracts")
def export_contracts(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    view_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),
    deal_id: UUID | None = Query(default=None),
    filters: str | None = Query(default=None, description="高级筛选 JSON"),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None, pattern="^(asc|desc)$"),
    ctx: TenantContext = Depends(
        require_any_permission(
            "crm.contract.list_own",
            "crm.contract.list_team",
            "crm.contract.list_all",
            "crm.contract.edit",
        )
    ),
    db: Session = Depends(get_db),
):
    export_filters = {
        "view_id": view_id,
        "q": q,
        "status": status,
        "customer_id": customer_id,
        "deal_id": deal_id,
        "filters": filters,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }
    if format == "xlsx":
        filename, content, row_count = export_service.export_xlsx(db, ctx, "contract", **export_filters)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        filename, content, row_count = export_service.export_csv(db, ctx, "contract", **export_filters)
        media = "text/csv; charset=utf-8"
    return _export_response(filename, content, media, row_count)
