"""平台公共招标线索池 Admin API（FR-TENDER-01/02/03）。"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_platform_admin
from app.models import User
from app.models.tender import TenderAttachment
from app.schemas.platform_tender import (
    ParseJobConfirmOut,
    ParseJobConfirmRequest,
    ParseJobOut,
    ParseTextRequest,
    PlatformTenderExcelConfirmOut,
    PlatformTenderExcelPreviewOut,
    PlatformTenderLeadCreate,
    PlatformTenderLeadListResponse,
    PlatformTenderLeadOut,
    PlatformTenderLeadUpdate,
)
from app.services import platform_tender_service as svc
from app.services import tender_parse_service as parse_svc

router = APIRouter(prefix="/admin/platform-tender-leads", tags=["admin-platform-tender"])


class ParseJobListResponse(BaseModel):
    items: list[ParseJobOut]
    total: int
    page: int
    page_size: int


@router.get("", response_model=PlatformTenderLeadListResponse)
def list_platform_tender_leads(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, description="关键词：采购方/标的/编号/代理/品目等"),
    region: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    category: str | None = Query(default=None),
    procurement_method: str | None = Query(default=None),
    agent_name: str | None = Query(default=None),
    project_no: str | None = Query(default=None),
    sme_preference: bool | None = Query(default=None),
    deadline_from: date | None = Query(default=None),
    deadline_to: date | None = Query(default=None),
    published_from: date | None = Query(default=None),
    published_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    items, total = svc.list_leads(
        db,
        status_filter=status,
        q=q,
        page=page,
        page_size=page_size,
        region=region,
        industry=industry,
        category=category,
        procurement_method=procurement_method,
        agent_name=agent_name,
        project_no=project_no,
        sme_preference=sme_preference,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        published_from=published_from,
        published_to=published_to,
    )
    return PlatformTenderLeadListResponse(
        items=[PlatformTenderLeadOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=PlatformTenderLeadOut, status_code=201)
def create_platform_tender_lead(
    body: PlatformTenderLeadCreate,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    return PlatformTenderLeadOut.model_validate(svc.create_lead(db, admin, body))


@router.get("/excel-template")
def download_excel_template(_: User = Depends(require_platform_admin)):
    data = svc.build_excel_template()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="platform_tender_leads_template.xlsx"'},
    )


@router.post("/excel/preview", response_model=PlatformTenderExcelPreviewOut)
async def preview_excel_import(
    file: UploadFile = File(...),
    _: User = Depends(require_platform_admin),
):
    content = await file.read()
    return svc.preview_excel(content)


@router.post("/excel/confirm", response_model=PlatformTenderExcelConfirmOut)
async def confirm_excel_import(
    file: UploadFile = File(...),
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    content = await file.read()
    return svc.confirm_excel(db, admin, content)


@router.post("/parse-attachment", response_model=ParseJobOut, status_code=201)
async def parse_attachment(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    job, should_schedule = parse_svc.enqueue_parse_attachment(db, admin, file)
    if should_schedule:
        background_tasks.add_task(parse_svc.run_parse_job, str(job.id))
    att = db.query(TenderAttachment).filter(TenderAttachment.id == job.attachment_id).first()
    return parse_svc._job_out(job, att)


@router.post("/parse-text", response_model=ParseJobOut, status_code=201)
def parse_text(
    body: ParseTextRequest,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """粘贴招投标正文 → 同一异步解析 + 人审确认链路。"""
    job, should_schedule = parse_svc.enqueue_parse_text(db, admin, body.text)
    if should_schedule:
        background_tasks.add_task(parse_svc.run_parse_job, str(job.id))
    att = db.query(TenderAttachment).filter(TenderAttachment.id == job.attachment_id).first()
    return parse_svc._job_out(job, att)


@router.get("/parse-jobs", response_model=ParseJobListResponse)
def list_parse_jobs(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    items, total = parse_svc.list_parse_jobs(db, status_filter=status, page=page, page_size=page_size)
    return ParseJobListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/parse-jobs/{job_id}", response_model=ParseJobOut)
def get_parse_job(
    job_id: UUID,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    return parse_svc.get_parse_job_detail(db, job_id)


@router.post("/parse-jobs/{job_id}/confirm", response_model=ParseJobConfirmOut)
def confirm_parse_job(
    job_id: UUID,
    body: ParseJobConfirmRequest,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    return parse_svc.confirm_parse_job(db, admin, job_id, body)


@router.get("/{lead_id}", response_model=PlatformTenderLeadOut)
def get_platform_tender_lead(
    lead_id: UUID,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    return PlatformTenderLeadOut.model_validate(svc.get_lead(db, lead_id))


@router.patch("/{lead_id}", response_model=PlatformTenderLeadOut)
def patch_platform_tender_lead(
    lead_id: UUID,
    body: PlatformTenderLeadUpdate,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    row = svc.get_lead(db, lead_id)
    return PlatformTenderLeadOut.model_validate(svc.update_lead(db, row, body))


@router.post("/{lead_id}/publish", response_model=PlatformTenderLeadOut)
def publish_platform_tender_lead(
    lead_id: UUID,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    row = svc.get_lead(db, lead_id)
    return PlatformTenderLeadOut.model_validate(svc.set_status(db, row, "published"))


@router.post("/{lead_id}/unpublish", response_model=PlatformTenderLeadOut)
def unpublish_platform_tender_lead(
    lead_id: UUID,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    row = svc.get_lead(db, lead_id)
    return PlatformTenderLeadOut.model_validate(svc.set_status(db, row, "unpublished"))


@router.delete("/{lead_id}", status_code=204)
def delete_platform_tender_lead(
    lead_id: UUID,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    row = svc.get_lead(db, lead_id)
    svc.delete_lead(db, row)
