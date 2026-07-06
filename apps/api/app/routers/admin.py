from uuid import UUID
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db, uuid_eq
from app.dependencies import require_platform_admin
from app.models import Content, IndustryPack, KnowledgeDocument, PlatformLLMConfig, Tenant, TenantMembership, User
from app.schemas import (
    AdminContentListResponse,
    AdminContentOut,
    AdminKnowledgeUploadTextRequest,
    AdminMembershipBrief,
    AdminTenantListResponse,
    AdminTenantMemberOut,
    AdminTenantOut,
    AdminTransferAdminRequest,
    AdminUserOut,
    AdminUserResetPasswordRequest,
    AdminUserUpdate,
    AssistantCreateRequest,
    AssistantOut,
    AssistantUpdateRequest,
    KnowledgeDocumentOut,
    LLMTestResponse,
    PlatformLLMSettingsOut,
    PlatformLLMSettingsUpdate,
    PlatformLLMTestRequest,
)
from app.services.auth_service import delete_user_account, reset_user_password
from app.services.admin_tenant_service import (
    get_tenant_admin,
    list_tenant_members_admin,
    list_tenants_admin,
    transfer_tenant_admin,
)
from app.services.crypto import decrypt_api_key, encrypt_api_key, mask_api_key
from app.services.llm.base import LLMMessage
from app.services.llm.factory import get_provider
from app.services.platform_llm_service import get_platform_config, resolve_platform_api_key
from app.services.knowledge_service import index_document

router = APIRouter(prefix="/admin", tags=["admin"])


def _content_out(content: Content) -> AdminContentOut:
    preview_url = None
    if content.preview_path:
        preview_url = f"/storage/published/{content.preview_path}"
    author = content.author
    tenant = author.tenant if author else None
    return AdminContentOut(
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
        author_name=author.display_name if author else "",
        author_phone=author.phone if author else None,
        tenant_name=tenant.name if tenant else "",
    )


def _doc_out(doc: KnowledgeDocument) -> KnowledgeDocumentOut:
    return KnowledgeDocumentOut(
        id=doc.id,
        title=doc.title,
        file_name=doc.file_name,
        scope=doc.scope,
        industry_code=doc.industry_code or "",
        status=doc.status,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
    )


def _user_out(user: User) -> AdminUserOut:
    memberships = [
        AdminMembershipBrief(
            tenant_id=m.tenant_id,
            tenant_name=m.tenant.name if m.tenant else "",
            role_code=m.role.code if m.role else "",
            role_name=m.role.name if m.role else "",
            is_active=m.is_active,
        )
        for m in user.memberships
    ]
    primary_tenant = user.tenant.name if user.tenant else ""
    if not primary_tenant and memberships:
        primary_tenant = memberships[0].tenant_name
    return AdminUserOut(
        id=user.id,
        phone=user.phone,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        tenant_name=primary_tenant,
        memberships=memberships,
        created_at=user.created_at,
    )


def _assistant_out(pack: IndustryPack) -> AssistantOut:
    return AssistantOut(
        code=pack.code,
        name=pack.name,
        description=pack.description or "",
        system_role=pack.system_role or "",
        compliance_rules=pack.compliance_rules or "",
        disclaimer=pack.disclaimer or "",
        default_tone=pack.default_tone or "专业亲切",
        welcome_message=pack.welcome_message or "",
        sort_order=pack.sort_order or 0,
        is_active=pack.is_active,
    )


@router.get("/assistants", response_model=list[AssistantOut])
def list_assistants_admin(
    q: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    from app.services.assistant_service import list_all_assistants

    return [_assistant_out(p) for p in list_all_assistants(db, q=q, is_active=is_active)]


@router.post("/assistants", response_model=AssistantOut)
def create_assistant(
    body: AssistantCreateRequest,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    if db.query(IndustryPack).filter(IndustryPack.code == body.code).first():
        raise HTTPException(status_code=400, detail="助手 code 已存在")
    pack = IndustryPack(
        code=body.code,
        name=body.name,
        description=body.description,
        system_role=body.system_role,
        compliance_rules=body.compliance_rules,
        disclaimer=body.disclaimer,
        default_tone=body.default_tone,
        welcome_message=body.welcome_message,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    db.add(pack)
    db.commit()
    db.refresh(pack)
    return _assistant_out(pack)


@router.patch("/assistants/{code}", response_model=AssistantOut)
def update_assistant(
    code: str,
    body: AssistantUpdateRequest,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    pack = db.query(IndustryPack).filter(IndustryPack.code == code).first()
    if not pack:
        raise HTTPException(status_code=404, detail="助手不存在")
    for field in (
        "name",
        "description",
        "system_role",
        "compliance_rules",
        "disclaimer",
        "default_tone",
        "welcome_message",
        "sort_order",
        "is_active",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(pack, field, value)
    db.commit()
    db.refresh(pack)
    return _assistant_out(pack)


@router.get("/contents", response_model=AdminContentListResponse)
def list_all_contents(
    status: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Content)
        .options(joinedload(Content.author).joinedload(User.tenant))
        .order_by(Content.created_at.desc())
    )
    if status:
        query = query.filter(Content.status == status)
    if platform:
        query = query.filter(Content.platform == platform)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(Content.topic.ilike(like))

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return AdminContentListResponse(
        items=[_content_out(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    q: str | None = Query(default=None),
    role: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    query = (
        db.query(User)
        .options(
            joinedload(User.tenant),
            joinedload(User.memberships)
            .joinedload(TenantMembership.tenant),
            joinedload(User.memberships)
            .joinedload(TenantMembership.role),
        )
        .outerjoin(Tenant, User.tenant_id == Tenant.id)
        .order_by(User.created_at.desc())
    )
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                User.phone.ilike(like),
                User.display_name.ilike(like),
                Tenant.name.ilike(like),
            )
        )
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))
    users = query.all()
    return [_user_out(u) for u in users]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: UUID,
    body: AdminUserUpdate,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .options(
            joinedload(User.tenant),
            joinedload(User.memberships)
            .joinedload(TenantMembership.tenant),
            joinedload(User.memberships)
            .joinedload(TenantMembership.role),
        )
        .filter(uuid_eq(User.id, user_id))
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id and body.is_active is False:
        raise HTTPException(status_code=400, detail="不能禁用当前登录账号")
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.display_name is not None:
        user.display_name = body.display_name
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.post("/users/{user_id}/reset-password", response_model=AdminUserOut)
def reset_password(
    user_id: UUID,
    body: AdminUserResetPasswordRequest,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    try:
        user = reset_user_password(db, user_id, body.password)
    except ValueError as e:
        if str(e) == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="用户不存在") from e
        raise
    return _user_out(user)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: UUID,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    try:
        delete_user_account(db, user_id, actor_id=admin.id)
    except ValueError as e:
        if str(e) == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="用户不存在") from e
        if str(e) == "CANNOT_DELETE_SELF":
            raise HTTPException(status_code=400, detail="不能删除当前登录账号") from e
        raise
    return {"ok": True}


@router.get("/tenants", response_model=AdminTenantListResponse)
def list_tenants(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    items, total = list_tenants_admin(db, q=q, page=page, page_size=page_size)
    return AdminTenantListResponse(
        items=[AdminTenantOut(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tenants/{tenant_id}", response_model=AdminTenantOut)
def get_tenant(
    tenant_id: UUID,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    item = get_tenant_admin(db, tenant_id)
    if not item:
        raise HTTPException(status_code=404, detail="企业不存在")
    return AdminTenantOut(**item)


@router.get("/tenants/{tenant_id}/members", response_model=list[AdminTenantMemberOut])
def list_tenant_members(
    tenant_id: UUID,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    if not get_tenant_admin(db, tenant_id):
        raise HTTPException(status_code=404, detail="企业不存在")
    rows = list_tenant_members_admin(db, tenant_id)
    return [AdminTenantMemberOut(**row) for row in rows]


@router.post("/tenants/{tenant_id}/transfer-admin")
def transfer_admin(
    tenant_id: UUID,
    body: AdminTransferAdminRequest,
    admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    try:
        transfer_tenant_admin(
            db,
            tenant_id,
            body.new_admin_user_id,
            actor_id=admin.id,
        )
    except ValueError as e:
        code = str(e)
        if code == "TENANT_NOT_FOUND":
            raise HTTPException(status_code=404, detail="企业不存在") from e
        if code == "MEMBER_NOT_FOUND":
            raise HTTPException(status_code=404, detail="成员不存在或未启用") from e
        if code == "ALREADY_ADMIN":
            raise HTTPException(status_code=400, detail="该成员已是企业管理员，无需转移") from e
        if code == "USER_INACTIVE":
            raise HTTPException(status_code=400, detail="目标账号已禁用") from e
        raise
    return {"ok": True}


@router.get("/knowledge/documents", response_model=list[KnowledgeDocumentOut])
def list_platform_knowledge(
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    docs = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.scope == "platform", KnowledgeDocument.tenant_id.is_(None))
        .order_by(KnowledgeDocument.created_at.desc())
        .all()
    )
    return [_doc_out(d) for d in docs]


@router.post("/knowledge/documents/text", response_model=KnowledgeDocumentOut)
def upload_platform_knowledge(
    body: AdminKnowledgeUploadTextRequest,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    doc = KnowledgeDocument(
        tenant_id=None,
        industry_code=body.industry_code,
        scope="platform",
        title=body.title,
        file_name=f"{body.title}.txt",
        raw_text=body.text,
        status="parsing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    index_document(db, doc)
    return _doc_out(doc)


@router.delete("/knowledge/documents/{document_id}")
def delete_platform_knowledge(
    document_id: UUID,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    doc = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.scope == "platform",
            KnowledgeDocument.tenant_id.is_(None),
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    db.delete(doc)
    db.commit()
    return {"ok": True}


def _platform_llm_out(row: PlatformLLMConfig) -> PlatformLLMSettingsOut:
    key = decrypt_api_key(row.api_key_encrypted) if row.api_key_encrypted else ""
    return PlatformLLMSettingsOut(
        provider=row.provider,
        base_url=row.base_url,
        model=row.model,
        timeout_sec=row.timeout_sec,
        default_free_quota=row.default_free_quota,
        is_active=row.is_active,
        api_key_masked=mask_api_key(key),
    )


@router.get("/platform-llm", response_model=PlatformLLMSettingsOut)
def get_platform_llm_settings(
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    row = get_platform_config(db)
    if not row:
        raise HTTPException(status_code=404, detail="平台 AI 配置不存在")
    return _platform_llm_out(row)


@router.patch("/platform-llm", response_model=PlatformLLMSettingsOut)
def update_platform_llm_settings(
    body: PlatformLLMSettingsUpdate,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    row = get_platform_config(db)
    if not row:
        row = PlatformLLMConfig()
        db.add(row)

    updates = body.model_dump(exclude_unset=True)
    api_key = updates.pop("api_key", None)
    for field, value in updates.items():
        setattr(row, field, value)
    if api_key:
        row.api_key_encrypted = encrypt_api_key(api_key)

    db.commit()
    db.refresh(row)
    return _platform_llm_out(row)


@router.post("/platform-llm/test", response_model=LLMTestResponse)
async def test_platform_llm_settings(
    body: PlatformLLMTestRequest | None = None,
    _: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    row = get_platform_config(db)
    provider = (body.provider if body and body.provider else None) or (row.provider if row else "deepseek")
    base_url = (body.base_url if body and body.base_url else None) or (row.base_url if row else "https://api.deepseek.com")
    model = (body.model if body and body.model else None) or (row.model if row else "deepseek-chat")
    timeout_sec = (body.timeout_sec if body and body.timeout_sec else None) or (row.timeout_sec if row else 60)

    api_key = ""
    if body and body.api_key:
        api_key = body.api_key
    elif row:
        api_key = resolve_platform_api_key(row)

    if not api_key:
        raise HTTPException(status_code=400, detail="请先保存 API Key，或在测试时填写 Key")

    llm = get_provider(provider)
    started = time.perf_counter()
    try:
        result = await llm.chat(
            [LLMMessage(role="user", content="请回复：连接成功")],
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout_sec=min(timeout_sec, 30),
        )
        latency = int((time.perf_counter() - started) * 1000)
        return LLMTestResponse(
            success=True,
            model=result.model,
            provider=provider,
            latency_ms=latency,
            message=result.content[:200],
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"模型连接失败: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"模型连接失败: {e}") from e
