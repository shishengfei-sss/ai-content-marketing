import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Content, User
from app.schemas import (
    CalendarEventOut,
    ContentGenerateRequest,
    ContentListResponse,
    ContentOut,
    ExportResponse,
    ReviewActionRequest,
    ScheduleRequest,
)
from app.services.content_service import (
    approve_content,
    get_content_for_tenant,
    reject_content,
    submit_for_review,
)
from app.services.export_service import export_douyin_markdown, export_xhs_zip
from app.services.knowledge_service import get_brand_profile, get_template, get_user_prompt, search_knowledge
from app.services.llm.base import LLMMessage
from app.services.llm_service import llm_service
from app.services.prompt_builder import build_system_prompt, build_user_prompt
from app.services.publish_service import execute_publish, reset_for_retry, schedule_content

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Content)
        .options(joinedload(Content.author))
        .filter(Content.tenant_id == current_user.tenant_id)
    )
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
    db: Session = Depends(get_db),
):
    items = (
        db.query(Content)
        .filter(
            Content.tenant_id == current_user.tenant_id,
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, current_user.tenant_id)
    return _content_out(content)


@router.post("/generate", response_model=ContentOut)
async def generate_content(
    body: ContentGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    system_prompt = build_system_prompt(body.platform)

    template = get_template(db, body.industry_code, body.platform, body.scene)
    rag_chunks = search_knowledge(
        db,
        tenant_id=current_user.tenant_id,
        industry_code=body.industry_code,
        query=f"{body.topic} {body.scene}",
    )
    brand = get_brand_profile(db, current_user.tenant_id)
    user_prompt_profile = get_user_prompt(db, current_user.id) if body.apply_user_prompt else None

    user_prompt = build_user_prompt(
        platform=body.platform,
        scene=body.scene,
        topic=body.topic,
        scene_name=template.name if template else "",
        template_hint=template.prompt_hint if template else "",
        rag_snippets=[c.content for c in rag_chunks],
        brand_name=brand.company_display_name if brand else "",
        brand_tone=brand.tone if brand else "",
        brand_cta=brand.cta_text if brand else "",
        brand_sample=brand.sample_snippet if brand else "",
        user_instructions=user_prompt_profile.global_instructions if user_prompt_profile else "",
        ephemeral_instruction=body.ephemeral_instruction,
    )

    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=user_prompt),
    ]

    try:
        result = await llm_service.chat(db, current_user.tenant_id, messages)
    except ValueError as e:
        if str(e) == "LLM_API_KEY_NOT_CONFIGURED":
            raise HTTPException(status_code=400, detail="请先在设置中配置 AI 模型 API Key") from e
        raise
    except httpx.HTTPError as e:
        logger.exception("LLM request failed")
        raise HTTPException(status_code=502, detail="模型连接失败，请检查 API Key 与网络") from e
    except Exception as e:
        logger.exception("LLM request failed")
        raise HTTPException(status_code=502, detail=f"生成失败: {e}") from e

    content = Content(
        tenant_id=current_user.tenant_id,
        author_id=current_user.id,
        industry_code=body.industry_code,
        platform=body.platform,
        scene=body.scene,
        topic=body.topic,
        body=result.content,
        status="draft",
        llm_provider=result.provider,
        llm_model=result.model,
    )
    db.add(content)
    db.commit()
    db.refresh(content)
    content = get_content_for_tenant(db, content.id, current_user.tenant_id)
    return _content_out(content)


@router.post("/{content_id}/submit-review", response_model=ContentOut)
def submit_review(
    content_id: UUID,
    body: ReviewActionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, current_user.tenant_id)
    content = submit_for_review(db, content, current_user, (body.comment if body else ""))
    content = get_content_for_tenant(db, content.id, current_user.tenant_id)
    return _content_out(content)


@router.post("/{content_id}/approve", response_model=ContentOut)
def approve(
    content_id: UUID,
    body: ReviewActionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, current_user.tenant_id)
    content = approve_content(db, content, current_user, (body.comment if body else ""))
    content = get_content_for_tenant(db, content.id, current_user.tenant_id)
    return _content_out(content)


@router.post("/{content_id}/reject", response_model=ContentOut)
def reject(
    content_id: UUID,
    body: ReviewActionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, current_user.tenant_id)
    content = reject_content(db, content, current_user, (body.comment if body else ""))
    content = get_content_for_tenant(db, content.id, current_user.tenant_id)
    return _content_out(content)


@router.post("/{content_id}/schedule", response_model=ContentOut)
def schedule(
    content_id: UUID,
    body: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, current_user.tenant_id)
    content = schedule_content(db, content, body.scheduled_at)
    content = get_content_for_tenant(db, content.id, current_user.tenant_id)
    return _content_out(content)


@router.post("/{content_id}/publish", response_model=ContentOut)
async def publish(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, current_user.tenant_id)
    content = await execute_publish(db, content)
    content = get_content_for_tenant(db, content.id, current_user.tenant_id)
    return _content_out(content)


@router.post("/{content_id}/retry-publish", response_model=ContentOut)
async def retry_publish(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, current_user.tenant_id)
    content = reset_for_retry(db, content)
    content = await execute_publish(db, content)
    content = get_content_for_tenant(db, content.id, current_user.tenant_id)
    return _content_out(content)


@router.post("/{content_id}/export/xhs", response_model=ExportResponse)
def export_xhs(
    content_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, current_user.tenant_id)
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
    db: Session = Depends(get_db),
):
    content = get_content_for_tenant(db, content_id, current_user.tenant_id)
    record, _ = export_douyin_markdown(db, content)
    return ExportResponse(
        export_id=record.id,
        export_type="douyin",
        download_url=f"/storage/exports/{record.file_name}",
        file_name=record.file_name,
    )
