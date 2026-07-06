import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import TenantContext, get_current_user, get_tenant_context, require_active_tenant_id
from app.models import Content, User
from app.schemas import (
    CalendarEventOut,
    ContentGenerateRequest,
    ContentListResponse,
    ContentOut,
    ContentProposalsRequest,
    ContentProposalsResponse,
    ExportResponse,
    ReviewActionRequest,
    ScheduleRequest,
)
from app.services.content_generation_service import run_generate_content, run_generate_proposals
from app.services.content_service import get_content_for_tenant
from app.services.export_service import export_douyin_markdown, export_video_script_markdown, export_xhs_zip
from app.services.publish_service import execute_publish, reset_for_retry, schedule_content
from app.services.scope_service import apply_content_list_scope, can_view_content

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["content"])


def _content_out(content: Content) -> ContentOut:
    preview_url = None
    if content.preview_path:
        preview_url = f"/storage/published/{content.preview_path}"
    return ContentOut(
        id=content.id,
        platform=content.platform,
        scene=content.scene,
        topic=content.topic,
        body=content.body,
        content_format=getattr(content, "content_format", "article") or "article",
        status=content.status,
        llm_provider=content.llm_provider,
        llm_model=content.llm_model,
        scheduled_at=content.scheduled_at,
        published_at=content.published_at,
        publish_error=content.publish_error,
        mock_read_count=content.mock_read_count or 0,
        preview_url=preview_url,
        created_at=content.created_at,
        updated_at=content.updated_at,
        author_name=content.author.display_name if content.author else "",
    )


@router.get("", response_model=ContentListResponse)
def list_contents(
    status: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Content)
        .options(joinedload(Content.author))
        .filter(Content.tenant_id == ctx.tenant_id)
    )
    query = apply_content_list_scope(query, ctx)
    if status:
        query = query.filter(Content.status == status)
    if platform:
        query = query.filter(Content.platform == platform)
    if q:
        query = query.filter(Content.topic.ilike(f"%{q}%"))

    total = query.count()
    items = (
        query.order_by(Content.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ContentListResponse(
        items=[_content_out(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/calendar", response_model=list[CalendarEventOut])
def calendar_events(
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    items = (
        db.query(Content)
        .filter(
            Content.tenant_id == tenant_id,
            Content.status.in_(["scheduled", "published"]),
            Content.scheduled_at.isnot(None),
        )
        .order_by(Content.scheduled_at.asc())
        .limit(100)
        .all()
    )
    return [
        CalendarEventOut(
            id=item.id,
            title=item.topic,
            platform=item.platform,
            scheduled_at=item.scheduled_at,
            status=item.status,
        )
        for item in items
        if item.scheduled_at
    ]


@router.get("/{content_id}", response_model=ContentOut)
def get_content(
    content_id: UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, ctx.tenant_id)
    if not can_view_content(ctx, content.author_id):
        raise HTTPException(status_code=403, detail="无权查看该内容")
    return _content_out(content)


@router.post("/proposals", response_model=ContentProposalsResponse)
async def generate_proposals(
    body: ContentProposalsRequest,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    return await run_generate_proposals(db, tenant_id, body)


@router.post("/generate", response_model=ContentOut)
async def generate_content(
    body: ContentGenerateRequest,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    content = await run_generate_content(db, tenant_id, current_user, body)
    return _content_out(content)


@router.post("/{content_id}/submit-review", include_in_schema=False)
def submit_review_removed(content_id: UUID):
    raise HTTPException(status_code=410, detail="审核流程已废止")


@router.post("/{content_id}/approve", include_in_schema=False)
def approve_removed(content_id: UUID):
    raise HTTPException(status_code=410, detail="审核流程已废止")


@router.post("/{content_id}/reject", include_in_schema=False)
def reject_removed(content_id: UUID):
    raise HTTPException(status_code=410, detail="审核流程已废止")


@router.post("/{content_id}/schedule", response_model=ContentOut)
def schedule(
    content_id: UUID,
    body: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, tenant_id)
    content = schedule_content(db, content, body.scheduled_at)
    content = get_content_for_tenant(db, content.id, tenant_id)
    return _content_out(content)


@router.post("/{content_id}/publish", response_model=ContentOut)
async def publish(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, tenant_id)
    content = await execute_publish(db, content)
    content = get_content_for_tenant(db, content.id, tenant_id)
    return _content_out(content)


@router.post("/{content_id}/retry-publish", response_model=ContentOut)
async def retry_publish(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, tenant_id)
    content = reset_for_retry(db, content)
    content = await execute_publish(db, content)
    content = get_content_for_tenant(db, content.id, tenant_id)
    return _content_out(content)


@router.post("/{content_id}/export/xhs", response_model=ExportResponse)
def export_xhs(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, tenant_id)
    record, _ = export_xhs_zip(db, content)
    return ExportResponse(
        export_id=record.id,
        export_type="xhs",
        download_url=f"/storage/exports/{record.file_name}",
        file_name=record.file_name,
    )


@router.post("/{content_id}/export/douyin", response_model=ExportResponse)
def export_douyin(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, tenant_id)
    record, _ = export_douyin_markdown(db, content)
    return ExportResponse(
        export_id=record.id,
        export_type="douyin",
        download_url=f"/storage/exports/{record.file_name}",
        file_name=record.file_name,
    )


@router.post("/{content_id}/export/script", response_model=ExportResponse)
def export_script(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, tenant_id)
    record, _ = export_video_script_markdown(db, content)
    return ExportResponse(
        export_id=record.id,
        export_type=record.export_type,
        download_url=f"/storage/exports/{record.file_name}",
        file_name=record.file_name,
    )
