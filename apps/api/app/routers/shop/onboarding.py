"""商家端入驻（A20）· 上传 + OCR + status + 自申/重提。"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import TenantContext, get_tenant_context
from app.schemas.shop_platform import (
    MerchantOnboardingStatusResponse,
    MerchantSelfOnboardingCreate,
    OnboardingApplicationOut,
    OnboardingFileUploadResponse,
    OnboardingOcrRequest,
    OnboardingOcrResponse,
)
from app.services.shop.onboarding_files import assert_onboarding_file_owned
from app.services.shop.onboarding_review_service import OCR_DOC_TYPES, run_onboarding_ocr
from app.services.shop.onboarding_service import (
    assert_self_onboarding_admin,
    create_merchant_self_onboarding,
    get_merchant_onboarding_status,
    resubmit_merchant_self_onboarding,
)

router = APIRouter(prefix="/onboarding", tags=["shop-onboarding"])

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


def require_self_onboarding(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    """A20 写接口：未入驻无商城角色，企业管理员自申；已入驻店铺管理员可补材料。店员 403。"""
    assert_self_onboarding_admin(ctx)
    return ctx


def _onboarding_upload_root(tenant_id: UUID) -> Path:
    root = Path(settings.STORAGE_DIR) / "shop_onboarding" / str(tenant_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


@router.get("/status", response_model=MerchantOnboardingStatusResponse)
def merchant_onboarding_status(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    return get_merchant_onboarding_status(db, ctx)


@router.post("/applications", response_model=OnboardingApplicationOut, status_code=201)
def merchant_submit_onboarding(
    payload: MerchantSelfOnboardingCreate,
    ctx: TenantContext = Depends(require_self_onboarding),
    db: Session = Depends(get_db),
):
    return create_merchant_self_onboarding(db, ctx, payload)


@router.put("/applications/{application_id}", response_model=OnboardingApplicationOut)
def merchant_resubmit_onboarding(
    application_id: UUID,
    payload: MerchantSelfOnboardingCreate,
    ctx: TenantContext = Depends(require_self_onboarding),
    db: Session = Depends(get_db),
):
    return resubmit_merchant_self_onboarding(db, ctx, application_id, payload)


@router.post("/files", response_model=OnboardingFileUploadResponse, status_code=201)
async def merchant_onboarding_upload_file(
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(require_self_onboarding),
):
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
    dest = _onboarding_upload_root(ctx.tenant_id) / f"{file_id}_{safe_name}"
    dest.write_bytes(content)
    return OnboardingFileUploadResponse(
        file_id=file_id,
        file_name=safe_name,
        doc_type=doc_type,
        size=len(content),
    )


@router.post("/ocr", response_model=OnboardingOcrResponse)
def merchant_onboarding_ocr(
    payload: OnboardingOcrRequest,
    ctx: TenantContext = Depends(require_self_onboarding),
):
    if not payload.file_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请先上传文件再识别")
    if payload.doc_type not in OCR_DOC_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="证件类型无效")
    assert_onboarding_file_owned(ctx.tenant_id, payload.file_id)
    result = run_onboarding_ocr(payload.doc_type, payload.file_id)
    return OnboardingOcrResponse(**result)
