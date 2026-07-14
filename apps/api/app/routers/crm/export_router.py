"""线索/客户导出 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.services.crm import export_service
from app.services.permission_service import require_any_permission

router = APIRouter(prefix="/export", tags=["crm-export"])


@router.get("/leads")
def export_leads(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    ctx: TenantContext = Depends(
        require_any_permission("crm.lead.list_own", "crm.lead.list_all", "crm.lead.edit")
    ),
    db: Session = Depends(get_db),
):
    if format == "xlsx":
        filename, content = export_service.export_xlsx(db, ctx.tenant_id, "lead")
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        filename, content = export_service.export_csv(db, ctx.tenant_id, "lead")
        media = "text/csv; charset=utf-8"
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/customers")
def export_customers(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    ctx: TenantContext = Depends(
        require_any_permission("crm.customer.list_own", "crm.customer.list_all", "crm.customer.edit")
    ),
    db: Session = Depends(get_db),
):
    if format == "xlsx":
        filename, content = export_service.export_xlsx(db, ctx.tenant_id, "customer")
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        filename, content = export_service.export_csv(db, ctx.tenant_id, "customer")
        media = "text/csv; charset=utf-8"
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
