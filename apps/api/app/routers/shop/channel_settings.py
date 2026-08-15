"""商家端公域对接设置 A23。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import TenantContext
from app.schemas.shop_platform import ChannelBindRequest, ChannelSettingOut, ChannelSettingSaveRequest
from app.services.permission_service import require_any_permission, require_permission
from app.services.shop import channel_service

router = APIRouter(prefix="/channel-settings", tags=["shop-channel-settings"])


@router.get("", response_model=ChannelSettingOut)
def get_settings(
    ctx: TenantContext = Depends(require_permission("shop.channel.read")),
    db: Session = Depends(get_db),
):
    return channel_service.settings_out(db, ctx.tenant_id)


@router.post("", response_model=ChannelSettingOut)
def save_settings(
    body: ChannelSettingSaveRequest,
    ctx: TenantContext = Depends(
        require_any_permission("shop.channel.write", "shop.channel.map")
    ),
    db: Session = Depends(get_db),
):
    return channel_service.save_settings(db, ctx, body)


@router.post("/bind", response_model=ChannelSettingOut)
def bind_shop(
    body: ChannelBindRequest,
    ctx: TenantContext = Depends(require_permission("shop.channel.write")),
    db: Session = Depends(get_db),
):
    return channel_service.bind_external_shop(
        db,
        ctx,
        shop_id=body.douyin_shop_id,
        secret=body.douyin_webhook_secret,
        bind_scope=body.bind_scope,
    )


@router.post("/send-test", response_model=ChannelSettingOut)
def send_test(
    ctx: TenantContext = Depends(require_permission("shop.channel.write")),
    db: Session = Depends(get_db),
):
    return channel_service.send_webhook_test(db, ctx)


@router.get("/webhook-url")
def webhook_url(
    ctx: TenantContext = Depends(require_permission("shop.channel.read")),
    db: Session = Depends(get_db),
):
    out = channel_service.settings_out(db, ctx.tenant_id)
    return {"webhook_url": out.webhook_url}
