"""P06 商户支付进件。对照 PRD 06#p06-onboarding-list · #p06e · #p06a–#p06d。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.shop_platform import PaymentOnboardingExportRequest, ShopExportTaskOut
from app.services.permission_service import require_platform_shop_any, require_platform_shop_permission
from app.services.shop import p06_channel_credential_service as credsvc
from app.services.shop import p06_payment_onboarding_service as p06svc

router = APIRouter(prefix="/payment-onboarding", tags=["platform-shop-payment-onboarding"])
_read = require_platform_shop_any("platform.shop.channel", "platform.shop.merchant.read")
_write = require_platform_shop_permission("platform.shop.channel")


def _base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


class ApproveBody(BaseModel):
    wx_sub_mch_id: str = Field(..., min_length=8, max_length=12)


class RejectBody(BaseModel):
    reason: str = Field(..., min_length=1)


class DoudianSaveBody(BaseModel):
    app_key: str = Field(..., min_length=1)
    app_secret: str | None = None


class DoudianRotateBody(BaseModel):
    app_secret: str = Field(..., min_length=1)


class WechatSaveBody(BaseModel):
    mch_id: str = Field(..., min_length=1)
    app_id: str = Field(..., min_length=1)
    api_v3_key: str | None = None
    cert_pem: str | None = None
    cert_key: str | None = None
    platform_pub: str | None = None


class WechatRotateCertBody(BaseModel):
    cert_pem: str = Field(..., min_length=1)
    cert_key: str = Field(..., min_length=1)


class WechatRotateV3Body(BaseModel):
    api_v3_key: str = Field(..., min_length=1)


@router.get("")
def list_onboardings(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    account_manager_user_id: str | None = Query(default=None),
    sort_by: str | None = Query(default="submitted_at"),
    sort_dir: str | None = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(_read),
    db: Session = Depends(get_db),
):
    return p06svc.list_onboardings(
        db,
        status=status,
        q=q,
        entity_type=entity_type,
        account_manager_user_id=account_manager_user_id,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.get("/export")
def export_onboardings(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    account_manager_user_id: str | None = Query(default=None),
    _: User = Depends(_read),
    db: Session = Depends(get_db),
):
    csv_text = p06svc.export_csv(
        db,
        status=status,
        q=q,
        entity_type=entity_type,
        account_manager_user_id=account_manager_user_id,
    )
    payload = "\ufeff" + csv_text
    return StreamingResponse(
        iter([payload.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-payment-onboarding.csv"'},
    )


@router.post("/export", response_model=ShopExportTaskOut)
def create_onboarding_export_task(
    body: PaymentOnboardingExportRequest | None = None,
    user: User = Depends(_read),
    db: Session = Depends(get_db),
):
    """对照 #p06-onboarding-list · 04#select-common：进件列表异步导出（站内信本批不接）。"""
    return p06svc.create_payment_onboarding_export_task(db, user, body)


@router.get("/export-tasks/{task_id}", response_model=ShopExportTaskOut)
def get_onboarding_export_task(
    task_id: UUID,
    user: User = Depends(_read),
    db: Session = Depends(get_db),
):
    return p06svc.get_payment_onboarding_export_task(db, user, task_id)


@router.get("/export-tasks/{task_id}/file")
def download_onboarding_export_file(
    task_id: UUID,
    user: User = Depends(_read),
    db: Session = Depends(get_db),
):
    csv_text = p06svc.read_payment_onboarding_export_file(db, user, task_id)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shop-payment-onboarding.csv"'},
    )


@router.get("/channel-config")
def get_channel_config(
    request: Request,
    _: User = Depends(_read),
    db: Session = Depends(get_db),
):
    return p06svc.channel_config(db, _base(request))


@router.put("/channel-config/doudian")
def save_doudian(
    body: DoudianSaveBody,
    request: Request,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return credsvc.save_doudian(
        db, user, app_key=body.app_key, app_secret=body.app_secret, base_url=_base(request)
    )


@router.post("/channel-config/doudian/rotate")
def rotate_doudian(
    body: DoudianRotateBody,
    request: Request,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return credsvc.rotate_doudian(db, user, app_secret=body.app_secret, base_url=_base(request))


@router.post("/channel-config/doudian/test")
def test_doudian(
    request: Request,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return credsvc.test_doudian(db, user, base_url=_base(request))


@router.put("/channel-config/wechat-pay")
def save_wechat(
    body: WechatSaveBody,
    request: Request,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return credsvc.save_wechat(
        db,
        user,
        mch_id=body.mch_id,
        app_id=body.app_id,
        api_v3_key=body.api_v3_key,
        cert_pem=body.cert_pem,
        cert_key=body.cert_key,
        platform_pub=body.platform_pub,
        base_url=_base(request),
    )


@router.post("/channel-config/wechat-pay/rotate-cert")
def rotate_wechat_cert(
    body: WechatRotateCertBody,
    request: Request,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return credsvc.rotate_wechat_cert(
        db, user, cert_pem=body.cert_pem, cert_key=body.cert_key, base_url=_base(request)
    )


@router.post("/channel-config/wechat-pay/rotate-v3")
def rotate_wechat_v3(
    body: WechatRotateV3Body,
    request: Request,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return credsvc.rotate_wechat_v3(db, user, api_v3_key=body.api_v3_key, base_url=_base(request))


@router.post("/channel-config/wechat-pay/test")
def test_wechat(
    request: Request,
    user: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return credsvc.test_wechat(db, user, base_url=_base(request))


@router.get("/{tenant_id}")
def get_onboarding(
    tenant_id: UUID,
    _: User = Depends(_read),
    db: Session = Depends(get_db),
):
    return p06svc.get_detail(db, tenant_id)


@router.post("/{tenant_id}/refresh")
def refresh_onboarding(
    tenant_id: UUID,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p06svc.refresh_status(db, tenant_id)


@router.post("/{tenant_id}/submit-wechat")
def submit_wechat(
    tenant_id: UUID,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p06svc.submit_wechat(db, tenant_id)


@router.post("/{tenant_id}/approve")
def approve_onboarding(
    tenant_id: UUID,
    body: ApproveBody,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p06svc.approve(db, tenant_id, wx_sub_mch_id=body.wx_sub_mch_id)


@router.post("/{tenant_id}/reject")
def reject_onboarding(
    tenant_id: UUID,
    body: RejectBody,
    _: User = Depends(_write),
    db: Session = Depends(get_db),
):
    return p06svc.reject(db, tenant_id, reason=body.reason)


@router.post("/{tenant_id}/reveal-sensitive")
def reveal_sensitive(
    tenant_id: UUID,
    _: User = Depends(_read),
    db: Session = Depends(get_db),
):
    return p06svc.reveal_sensitive(db, tenant_id)


@router.post("/{tenant_id}/notify")
def notify_merchant(
    tenant_id: UUID,
    _: User = Depends(_read),
    db: Session = Depends(get_db),
):
    return p06svc.notify_merchant(db, tenant_id)
