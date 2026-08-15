"""平台入驻代发起 API（P02-A）。"""

from __future__ import annotations

import re
import uuid
from datetime import date
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, uuid_eq
from app.dependencies import require_platform_admin
from app.models import User
from app.models.shop import ShopOnboardingApplication
from app.schemas.shop_platform import (
    MerchantRevealRequest,
    MerchantRevealResponse,
    OnboardingApplicationCreate,
    OnboardingApplicationDetail,
    OnboardingApplicationListResponse,
    OnboardingApplicationOut,
    OnboardingApproveOptionsResponse,
    OnboardingApproveRequest,
    OnboardingApproveResponse,
    OnboardingFileUploadResponse,
    OnboardingOcrRequest,
    OnboardingOcrResponse,
    OnboardingPrefillResponse,
    OnboardingRejectReasonsResponse,
    OnboardingRejectRequest,
    TenantOnboardingSearchResponse,
)
from app.services.permission_service import require_platform_shop_any, require_platform_shop_permission
from app.services.platform_shop_service import assert_can_initiate_onboarding
from app.services.shop.onboarding_files import (
    assert_onboarding_file_owned,
    resolve_onboarding_stored_file,
)
from app.services.shop.onboarding_review_service import (
    OCR_DOC_TYPES,
    approve_onboarding_application,
    get_onboarding_application_detail,
    list_onboarding_applications,
    list_onboarding_approve_options,
    list_onboarding_reject_reasons,
    reject_onboarding_application,
    reveal_onboarding_sensitive,
    run_onboarding_ocr,
)
from app.services.shop.onboarding_service import (
    create_onboarding_application,
    get_onboarding_prefill,
    search_onboarding_tenant_options,
)

router = APIRouter(prefix="/onboarding", tags=["platform-shop-onboarding"])

_UPLOAD_DOC_TYPES = frozenset(
    {
        "id_card_front",
        "id_card_back",
        "handheld",
        "business_license",
        "legal_id_front",
        "legal_id_back",
        "other",
    }
)
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_SAFE_NAME = re.compile(r"[^\w.\u4e00-\u9fff\-]+")


def _platform_upload_root(tenant_id: UUID) -> Path:
    root = Path(settings.STORAGE_DIR) / "shop_onboarding" / str(tenant_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_onboarding_file(tenant_id: UUID, file_id: str) -> Path | None:
    return resolve_onboarding_stored_file(tenant_id, file_id)


@router.get("/tenant-options", response_model=TenantOnboardingSearchResponse)
def list_tenant_options(
    q: str | None = Query(default=None, description="租户名 / 信用代码"),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(require_platform_shop_permission("platform.shop.onboarding.initiate")),
    db: Session = Depends(get_db),
):
    assert_can_initiate_onboarding(user)
    return search_onboarding_tenant_options(db, user=user, q=q, limit=limit)


@router.get("/tenants/{tenant_id}/prefill", response_model=OnboardingPrefillResponse)
def get_tenant_prefill(
    tenant_id: UUID,
    user: User = Depends(require_platform_shop_permission("platform.shop.onboarding.initiate")),
    db: Session = Depends(get_db),
):
    assert_can_initiate_onboarding(user)
    return get_onboarding_prefill(db, tenant_id)


@router.post("/applications", response_model=OnboardingApplicationOut, status_code=201)
def submit_onboarding_application(
    payload: OnboardingApplicationCreate,
    user: User = Depends(require_platform_shop_permission("platform.shop.onboarding.initiate")),
    db: Session = Depends(get_db),
):
    assert_can_initiate_onboarding(user)
    return create_onboarding_application(db, user, payload)


@router.get("/applications", response_model=OnboardingApplicationListResponse)
def list_applications(
    q: str | None = Query(default=None, description="搜索商家名"),
    status: str | None = Query(default=None, description="pending|approved|rejected"),
    entity_type: str | None = Query(default=None),
    initiator: str | None = Query(default=None, description="merchant_self|platform"),
    submitted_from: date | None = Query(default=None),
    submitted_until: date | None = Query(default=None),
    sort_by: str | None = Query(default="submitted_at", description="display_name|submitted_at"),
    sort_dir: str | None = Query(default="desc", description="asc|desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.approve",
            "platform.shop.onboarding.initiate",
            "platform.shop.merchant.read",
        )
    ),
    db: Session = Depends(get_db),
):
    return list_onboarding_applications(
        db,
        user,
        q=q,
        status_filter=status,
        entity_type=entity_type,
        initiator=initiator,
        submitted_from=submitted_from,
        submitted_until=submitted_until,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.get("/applications/{application_id}", response_model=OnboardingApplicationDetail)
def get_application_detail(
    application_id: UUID,
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.approve",
            "platform.shop.onboarding.initiate",
            "platform.shop.merchant.read",
        )
    ),
    db: Session = Depends(get_db),
):
    return get_onboarding_application_detail(db, user, application_id)


@router.post("/applications/{application_id}/reveal-sensitive", response_model=MerchantRevealResponse)
def reveal_application_sensitive(
    application_id: UUID,
    body: MerchantRevealRequest | None = None,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """对照 #p03-detail-sensitive：揭露经营联系人手机 / 身份证号 / 对公账号。GET 详情永不返回明文。"""
    field = body.field if body is not None else "contact_mobile"
    return reveal_onboarding_sensitive(db, user, application_id, field)


@router.get("/reject-reasons", response_model=OnboardingRejectReasonsResponse)
def get_reject_reasons(
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.approve",
            "platform.shop.onboarding.initiate",
            "platform.shop.merchant.read",
        )
    ),
):
    return list_onboarding_reject_reasons()


@router.get("/approve-options", response_model=OnboardingApproveOptionsResponse)
def get_approve_options(
    entity_type: str | None = Query(default=None),
    user: User = Depends(require_platform_shop_permission("platform.shop.approve")),
    db: Session = Depends(get_db),
):
    return list_onboarding_approve_options(db, user, entity_type=entity_type)


@router.post("/applications/{application_id}/approve", response_model=OnboardingApproveResponse)
def approve_application(
    application_id: UUID,
    payload: OnboardingApproveRequest,
    user: User = Depends(require_platform_shop_permission("platform.shop.approve")),
    db: Session = Depends(get_db),
):
    return approve_onboarding_application(db, user, application_id, payload)


@router.post("/applications/{application_id}/reject", response_model=OnboardingApplicationDetail)
def reject_application(
    application_id: UUID,
    payload: OnboardingRejectRequest,
    user: User = Depends(require_platform_shop_permission("platform.shop.approve")),
    db: Session = Depends(get_db),
):
    return reject_onboarding_application(db, user, application_id, payload)


@router.get("/applications/{application_id}/files/{file_id}")
def download_application_file(
    application_id: UUID,
    file_id: str,
    user: User = Depends(
        require_platform_shop_any(
            "platform.shop.approve",
            "platform.shop.onboarding.initiate",
            "platform.shop.merchant.read",
        )
    ),
    db: Session = Depends(get_db),
):
    """审核详情预览/下载资质附件（须属于该申请的 qualification_files）。"""
    app = (
        db.query(ShopOnboardingApplication)
        .filter(uuid_eq(ShopOnboardingApplication.id, application_id))
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="入驻申请不存在")
    files = app.qualification_files or {}
    allowed = {str(v) for v in files.values() if v}
    if file_id not in allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在或不属于该申请")
    path = _resolve_onboarding_file(app.tenant_id, file_id)
    if not path or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件文件已丢失")
    # 触发一次权限门禁（与详情一致）
    get_onboarding_application_detail(db, user, application_id)
    name = path.name.split("_", 1)[-1] if "_" in path.name else path.name
    suffix = path.suffix.lower()
    media = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")
    return FileResponse(path, filename=name, media_type=media)


@router.post("/files", response_model=OnboardingFileUploadResponse, status_code=201)
async def platform_onboarding_upload_file(
    tenant_id: UUID = Form(...),
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_platform_shop_permission("platform.shop.onboarding.initiate")),
):
    assert_can_initiate_onboarding(user)
    if doc_type not in _UPLOAD_DOC_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="证件类型无效")
    raw_name = (file.filename or "upload.bin").strip() or "upload.bin"
    safe_name = _SAFE_NAME.sub("_", raw_name)[:120]
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文件为空")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文件不能超过 10MB")

    file_id = str(uuid.uuid4())
    dest = _platform_upload_root(tenant_id) / f"{file_id}_{safe_name}"
    dest.write_bytes(content)
    return OnboardingFileUploadResponse(
        file_id=file_id,
        file_name=safe_name,
        doc_type=doc_type,
        size=len(content),
    )


@router.post("/ocr", response_model=OnboardingOcrResponse)
def platform_onboarding_ocr(
    payload: OnboardingOcrRequest,
    user: User = Depends(require_platform_shop_permission("platform.shop.onboarding.initiate")),
):
    assert_can_initiate_onboarding(user)
    if not payload.file_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请先上传文件再识别")
    if payload.doc_type not in OCR_DOC_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="证件类型无效")
    if payload.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请指定关联租户后再识别")
    assert_onboarding_file_owned(payload.tenant_id, payload.file_id)
    result = run_onboarding_ocr(payload.doc_type, payload.file_id)
    return OnboardingOcrResponse(**result)
