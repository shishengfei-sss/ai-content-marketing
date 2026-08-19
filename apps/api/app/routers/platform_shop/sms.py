"""P12 短信管理。对照 PRD 06#p12。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.shop_platform import (
    ShopExportTaskOut,
    SmsAssignmentExportRequest,
    SmsLogExportRequest,
    SmsSignatureExportRequest,
    SmsTemplateExportRequest,
)
from app.services.permission_service import require_platform_shop_any, require_platform_shop_permission
from app.services.shop import p12_sms_service as p12svc

router = APIRouter(prefix="/sms", tags=["platform-shop-sms"])

_read_logs = require_platform_shop_any("platform.shop.channel", "platform.shop.merchant.read")
_write = require_platform_shop_permission("platform.shop.channel")


class SignatureCreate(BaseModel):
    tenant_id: UUID
    content: str
    remark: str | None = None
    qualification_files: dict | None = None


class SignatureResubmit(BaseModel):
    content: str | None = None
    remark: str | None = None
    qualification_files: dict | None = None


class RejectBody(BaseModel):
    reason: str = Field(..., min_length=1)


class TemplateCreate(BaseModel):
    name: str
    template_code: str
    purpose: str
    content_preview: str | None = None
    is_default_claim: bool = False


class TemplateUpdate(BaseModel):
    name: str | None = None
    content_preview: str | None = None


class AssignBody(BaseModel):
    tenant_id: UUID
    sms_signature_id: UUID
    claim_template_id: UUID


class ChannelSaveBody(BaseModel):
    access_key_id: str | None = None
    access_key_secret: str | None = None
    default_notify_signature: str | None = None


@router.get("/channel-config")
def channel_config(_: User = Depends(_read_logs), db: Session = Depends(get_db)):
    return p12svc.channel_config(db)


@router.put("/channel-config")
def save_channel_config(
    body: ChannelSaveBody,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.save_channel_config(
        db,
        user,
        access_key_id=body.access_key_id,
        access_key_secret=body.access_key_secret,
        default_notify_signature=body.default_notify_signature,
    )


@router.post("/channel-config/test")
def test_channel_config(
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.test_channel_config(db, user)


@router.get("/merchant-options")
def merchant_options(_: User = Depends(_write), db: Session = Depends(get_db)):
    return {"items": p12svc.merchant_options(db)}


@router.get("/signatures")
def list_signatures(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.list_signatures(db, q=q, status=status, page=page, page_size=page_size)


@router.get("/signatures/export")
def export_signatures(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    csv_text = p12svc.export_signatures_csv(db, q=q, status=status)
    payload = "\ufeff" + csv_text
    return StreamingResponse(
        iter([payload.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-sms-signatures.csv"'},
    )


@router.post("/signatures/export", response_model=ShopExportTaskOut)
def create_signature_export_task(
    body: SmsSignatureExportRequest | None = None,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    """对照 #p12-signatures · 04#select-common：签名列表异步导出（站内信本批不接）。"""
    return p12svc.create_signature_export_task(db, user, body)


@router.get("/signatures/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_signature_export_task(
    task_id: UUID,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.get_signature_export_task(db, user, task_id)


@router.get("/signatures/export-tasks/{task_id}/file")
def download_signature_export_file(
    task_id: UUID,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    csv_text = p12svc.read_signature_export_file(db, user, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-sms-signatures.csv"'},
    )


@router.post("/signatures")
def create_signature(
    body: SignatureCreate,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.create_signature(
        db,
        tenant_id=body.tenant_id,
        content=body.content,
        remark=body.remark,
        qualification_files=body.qualification_files,
    )


@router.get("/signatures/{sig_id}")
def get_signature(
    sig_id: UUID,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.get_signature(db, sig_id)


@router.post("/signatures/{sig_id}/sync")
def sync_signature(
    sig_id: UUID,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.sync_signature(db, sig_id)


@router.post("/signatures/{sig_id}/withdraw")
def withdraw_signature(
    sig_id: UUID,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.withdraw_signature(db, sig_id)


@router.post("/signatures/{sig_id}/approve")
def approve_signature(
    sig_id: UUID,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.approve_signature(db, sig_id)


@router.post("/signatures/{sig_id}/reject")
def reject_signature(
    sig_id: UUID,
    body: RejectBody,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.reject_signature(db, sig_id, reason=body.reason)


@router.post("/signatures/{sig_id}/resubmit")
def resubmit_signature(
    sig_id: UUID,
    body: SignatureResubmit,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.resubmit_signature(
        db,
        sig_id,
        content=body.content,
        remark=body.remark,
        qualification_files=body.qualification_files,
    )


@router.get("/templates")
def list_templates(
    purpose: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.list_templates(db, purpose=purpose, status=status, page=page, page_size=page_size)


@router.get("/templates/export")
def export_templates(
    purpose: str | None = Query(default=None),
    status: str | None = Query(default=None),
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    csv_text = p12svc.export_templates_csv(db, purpose=purpose, status=status)
    payload = "\ufeff" + csv_text
    return StreamingResponse(
        iter([payload.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-sms-templates.csv"'},
    )


@router.post("/templates/export", response_model=ShopExportTaskOut)
def create_template_export_task(
    body: SmsTemplateExportRequest | None = None,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    """对照 #p12-templates · 04#select-common：模板列表异步导出（站内信本批不接）。"""
    return p12svc.create_template_export_task(db, user, body)


@router.get("/templates/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_template_export_task(
    task_id: UUID,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.get_template_export_task(db, user, task_id)


@router.get("/templates/export-tasks/{task_id}/file")
def download_template_export_file(
    task_id: UUID,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    csv_text = p12svc.read_template_export_file(db, user, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-sms-templates.csv"'},
    )


@router.post("/templates")
def create_template(
    body: TemplateCreate,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.create_template(
        db,
        name=body.name,
        template_code=body.template_code,
        purpose=body.purpose,
        content_preview=body.content_preview,
        is_default_claim=body.is_default_claim,
    )


@router.patch("/templates/{tpl_id}")
def update_template(
    tpl_id: UUID,
    body: TemplateUpdate,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.update_template(db, tpl_id, name=body.name, content_preview=body.content_preview)


@router.post("/templates/{tpl_id}/set-default")
def set_default_template(
    tpl_id: UUID,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.set_default_claim(db, tpl_id)


@router.get("/assignments")
def list_assignments(
    q: str | None = Query(default=None),
    assign_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.list_assignments(
        db, q=q, assign_status=assign_status, page=page, page_size=page_size
    )


@router.get("/assignments/export")
def export_assignments(
    q: str | None = Query(default=None),
    assign_status: str | None = Query(default=None),
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    csv_text = p12svc.export_assignments_csv(db, q=q, assign_status=assign_status)
    payload = "\ufeff" + csv_text
    return StreamingResponse(
        iter([payload.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-sms-assignments.csv"'},
    )


@router.post("/assignments/export", response_model=ShopExportTaskOut)
def create_assignment_export_task(
    body: SmsAssignmentExportRequest | None = None,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    """对照 #p12-assign · 04#select-common：商家分配异步导出（站内信本批不接）。"""
    return p12svc.create_assignment_export_task(db, user, body)


@router.get("/assignments/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_assignment_export_task(
    task_id: UUID,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.get_assignment_export_task(db, user, task_id)


@router.get("/assignments/export-tasks/{task_id}/file")
def download_assignment_export_file(
    task_id: UUID,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    csv_text = p12svc.read_assignment_export_file(db, user, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-sms-assignments.csv"'},
    )


@router.get("/assignments/options")
def assignment_options(
    tenant_id: UUID = Query(...),
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return {
        "signatures": p12svc.approved_signatures_for(db, tenant_id),
        "templates": p12svc.approved_claim_templates(db),
    }


@router.post("/assignments")
def assign_sms(
    body: AssignBody,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.assign_sms(
        db,
        tenant_id=body.tenant_id,
        sms_signature_id=body.sms_signature_id,
        claim_template_id=body.claim_template_id,
    )


@router.get("/logs")
def list_logs(
    purpose: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    range_key: str | None = Query(default="30d"),
    date_from: str | None = Query(default=None),
    date_until: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(_read_logs),
    db: Session = Depends(get_db),
):
    return p12svc.list_logs(
        db,
        purpose=purpose,
        status=status,
        q=q,
        range_key=range_key,
        date_from=date_from,
        date_until=date_until,
        page=page,
        page_size=page_size,
    )


@router.get("/logs/export")
def export_logs(
    purpose: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    range_key: str | None = Query(default="30d"),
    date_from: str | None = Query(default=None),
    date_until: str | None = Query(default=None),
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    csv_text = p12svc.export_logs_csv(
        db,
        purpose=purpose,
        status=status,
        q=q,
        range_key=range_key,
        date_from=date_from,
        date_until=date_until,
    )
    payload = "\ufeff" + csv_text
    return StreamingResponse(
        iter([payload.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-sms-logs.csv"'},
    )


@router.post("/logs/export", response_model=ShopExportTaskOut)
def create_logs_export_task(
    body: SmsLogExportRequest | None = None,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    """对照 #p12-logs：发送记录异步导出（时间≤31天；站内信本批不接）。"""
    return p12svc.create_sms_log_export_task(db, user, body)


@router.get("/logs/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_logs_export_task(
    task_id: UUID,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.get_sms_log_export_task(db, user, task_id)


@router.get("/logs/export-tasks/{task_id}/file")
def download_logs_export_file(
    task_id: UUID,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    csv_text = p12svc.read_sms_log_export_file(db, user, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-sms-logs.csv"'},
    )


@router.get("/logs/{log_id}")
def get_log(
    log_id: UUID,
    _: User = Depends(_read_logs),
    db: Session = Depends(get_db),
):
    return p12svc.get_log(db, log_id)


@router.post("/logs/{log_id}/reveal-mobile")
def reveal_mobile(
    log_id: UUID,
    _: User = Depends(_read_logs),
    db: Session = Depends(get_db),
):
    return p12svc.get_log(db, log_id, reveal=True)


@router.post("/logs/{log_id}/retry")
def retry_log(
    log_id: UUID,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p12svc.retry_log(db, log_id)
