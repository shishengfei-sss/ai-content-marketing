import html
import logging
import random
from pathlib import Path
from uuid import UUID

from app.config import settings
from app.services.publish.base import PublishResult, PublishStats, WeChatPublisher

logger = logging.getLogger(__name__)


class MockWeChatPublisher(WeChatPublisher):
    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or settings.storage_published_dir

    async def publish(
        self,
        *,
        content_id: UUID,
        topic: str,
        body: str,
        tenant_id: UUID,
    ) -> PublishResult:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{content_id}.html"
        file_path = self.storage_dir / filename

        safe_topic = html.escape(topic or "未命名文章")
        safe_body = html.escape(body or "")
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_topic}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           max-width: 720px; margin: 40px auto; padding: 0 16px; line-height: 1.8; color: #333; }}
    h1 {{ font-size: 24px; margin-bottom: 24px; }}
    .meta {{ color: #999; font-size: 13px; margin-bottom: 32px; }}
    .body {{ white-space: pre-wrap; }}
    .mock-badge {{ background: #fff7e6; color: #d48806; padding: 8px 12px;
                   border-radius: 6px; font-size: 13px; margin-bottom: 24px; }}
  </style>
</head>
<body>
  <div class="mock-badge">Mock 预览 — 开发环境模拟发布，非真实微信文章</div>
  <h1>{safe_topic}</h1>
  <div class="meta">租户 {html.escape(str(tenant_id)[:8])}… · Mock 微信公众号</div>
  <div class="body">{safe_body}</div>
</body>
</html>
"""
        file_path.write_text(html_content, encoding="utf-8")
        mock_reads = random.randint(120, 680)
        logger.info("Mock published content %s to %s", content_id, file_path)
        return PublishResult(
            success=True,
            preview_path=filename,
            mock_read_count=mock_reads,
            external_id=f"mock-{content_id}",
            message="Mock 发布成功",
        )

    async def get_stats(self, external_id: str) -> PublishStats:
        return PublishStats(read_count=random.randint(50, 500), share_count=random.randint(5, 80))


class RealWeChatPublisher(WeChatPublisher):
    async def publish(
        self,
        *,
        content_id: UUID,
        topic: str,
        body: str,
        tenant_id: UUID,
    ) -> PublishResult:
        raise NotImplementedError("RealWeChatPublisher 将在部署阶段实现，请使用 WECHAT_PUBLISHER=mock")

    async def get_stats(self, external_id: str) -> PublishStats:
        raise NotImplementedError("RealWeChatPublisher 将在部署阶段实现")
