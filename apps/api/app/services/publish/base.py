from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class PublishResult:
    success: bool
    preview_path: str = ""
    mock_read_count: int = 0
    external_id: str = ""
    message: str = ""


@dataclass
class PublishStats:
    read_count: int = 0
    share_count: int = 0


class WeChatPublisher:
    async def publish(
        self,
        *,
        content_id: UUID,
        topic: str,
        body: str,
        tenant_id: UUID,
    ) -> PublishResult:
        raise NotImplementedError

    async def get_stats(self, external_id: str) -> PublishStats:
        raise NotImplementedError
