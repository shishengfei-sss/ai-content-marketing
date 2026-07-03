from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import WeChatBindRequest, WeChatSettingsOut
from app.services.publish_service import bind_mock_wechat, get_wechat_account

router = APIRouter(prefix="/settings/wechat", tags=["wechat-settings"])


@router.get("", response_model=WeChatSettingsOut)
def get_wechat_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_wechat_account(db, current_user.tenant_id)
    return WeChatSettingsOut(
        bound=account is not None,
        account_name=account.account_name if account else "",
        mode=settings.WECHAT_PUBLISHER,
        is_mock=account.is_mock if account else settings.WECHAT_PUBLISHER == "mock",
    )


@router.post("/bind-mock", response_model=WeChatSettingsOut)
def bind_mock(
    body: WeChatBindRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if settings.WECHAT_PUBLISHER != "mock":
        raise HTTPException(status_code=400, detail="当前非 Mock 模式，请使用真实 OAuth 绑定")

    account = bind_mock_wechat(db, current_user.tenant_id, body.account_name)
    return WeChatSettingsOut(
        bound=True,
        account_name=account.account_name,
        mode=settings.WECHAT_PUBLISHER,
        is_mock=True,
    )
