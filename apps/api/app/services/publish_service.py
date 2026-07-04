"""公众号发布服务（开发期默认 Mock）。

发布流：draft/scheduled → publishing → published | failed。
MVP 仅 wechat 平台可发布；失败后可 reset 为 draft 再重试。
定时到点发布由 main.py 内 asyncio 轮询触发（开发期替代 Celery）。
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Content, PlatformAccount, PublishLog
from app.services.publish.factory import get_wechat_publisher

logger = logging.getLogger(__name__)

PUBLISHABLE_PLATFORM = "wechat"


def assert_wechat_content(content: Content) -> None:
    if content.platform != PUBLISHABLE_PLATFORM:
        raise HTTPException(status_code=400, detail="当前仅支持公众号（wechat）内容发布")


def assert_wechat_auto_publishable(db: Session, content: Content) -> None:
    assert_wechat_content(content)
    if getattr(content, "content_format", "article") != "article":
        raise HTTPException(
            status_code=400,
            detail="视频脚本不支持自动发布，请复制或下载脚本后手动制作视频",
        )
    account = get_wechat_account(db, content.tenant_id)
    if not account:
        raise HTTPException(status_code=400, detail="请先在设置中绑定公众号")
    if account.account_type == "subscription":
        raise HTTPException(
            status_code=400,
            detail="订阅号不支持自动发布，请复制或下载内容后到公众号后台手动发表",
        )


def assert_publishable_status(content: Content, *, allow_failed: bool = False) -> None:
    allowed = {"draft", "scheduled"}
    if allow_failed:
        allowed = allowed | {"failed"}
    if content.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态「{content.status}」不能发布",
        )


def _log_publish(
    db: Session,
    content: Content,
    action: str,
    status: str,
    message: str,
) -> None:
    db.add(
        PublishLog(
            content_id=content.id,
            tenant_id=content.tenant_id,
            action=action,
            status=status,
            message=message,
        )
    )


async def execute_publish(db: Session, content: Content) -> Content:
    assert_wechat_auto_publishable(db, content)
    assert_publishable_status(content, allow_failed=True)

    content.status = "publishing"
    content.publish_error = None
    db.commit()

    publisher = get_wechat_publisher()
    try:
        result = await publisher.publish(
            content_id=content.id,
            topic=content.topic,
            body=content.body,
            tenant_id=content.tenant_id,
        )
    except NotImplementedError as e:
        content.status = "failed"
        content.publish_error = str(e)
        _log_publish(db, content, "publish", "failed", str(e))
        db.commit()
        db.refresh(content)
        raise HTTPException(status_code=501, detail=str(e)) from e
    except Exception as e:
        logger.exception("Publish failed for content %s", content.id)
        content.status = "failed"
        content.publish_error = str(e)
        _log_publish(db, content, "publish", "failed", str(e))
        db.commit()
        db.refresh(content)
        raise HTTPException(status_code=502, detail=f"发布失败: {e}") from e

    if not result.success:
        content.status = "failed"
        content.publish_error = result.message or "发布失败"
        _log_publish(db, content, "publish", "failed", content.publish_error)
        db.commit()
        db.refresh(content)
        raise HTTPException(status_code=502, detail=content.publish_error)

    now = datetime.now(timezone.utc)
    content.status = "published"
    content.published_at = now
    content.preview_path = result.preview_path
    content.mock_read_count = result.mock_read_count
    content.publish_error = None
    _log_publish(db, content, "publish", "success", result.message)
    db.commit()
    db.refresh(content)
    return content


def schedule_content(db: Session, content: Content, scheduled_at: datetime) -> Content:
    assert_wechat_auto_publishable(db, content)
    if content.status not in {"draft", "failed", "scheduled"}:
        raise HTTPException(status_code=400, detail="当前状态不能排期")

    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

    if scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="排期时间须晚于当前时间")

    content.status = "scheduled"
    content.scheduled_at = scheduled_at
    content.publish_error = None
    _log_publish(
        db,
        content,
        "schedule",
        "success",
        f"已排期至 {scheduled_at.isoformat()}",
    )
    db.commit()
    db.refresh(content)
    return content


def reset_for_retry(db: Session, content: Content) -> Content:
    """发布失败后回到 draft，以便再次 execute_publish。"""
    if content.status != "failed":
        raise HTTPException(status_code=400, detail="仅失败状态可重试")
    content.status = "draft"
    content.publish_error = None
    db.commit()
    db.refresh(content)
    return content


async def process_due_scheduled_async(db: Session) -> int:
    now = datetime.now(timezone.utc)
    due_items = (
        db.query(Content)
        .filter(
            Content.status == "scheduled",
            Content.scheduled_at.isnot(None),
            Content.scheduled_at <= now,
        )
        .all()
    )
    count = 0
    for content in due_items:
        try:
            await execute_publish(db, content)
            count += 1
        except HTTPException:
            logger.warning("Scheduled publish failed for %s", content.id)
        except Exception:
            logger.exception("Scheduled publish error for %s", content.id)
    return count


def get_wechat_account(db: Session, tenant_id: UUID) -> PlatformAccount | None:
    return (
        db.query(PlatformAccount)
        .filter(
            PlatformAccount.tenant_id == tenant_id,
            PlatformAccount.platform == "wechat",
            PlatformAccount.is_active.is_(True),
        )
        .first()
    )


def bind_mock_wechat(
    db: Session, tenant_id: UUID, account_name: str, account_type: str = "service"
) -> PlatformAccount:
    existing = get_wechat_account(db, tenant_id)
    if existing:
        existing.account_name = account_name
        existing.account_type = account_type
        existing.is_mock = True
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    account = PlatformAccount(
        tenant_id=tenant_id,
        platform="wechat",
        account_name=account_name,
        account_type=account_type,
        is_mock=True,
        is_active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account
