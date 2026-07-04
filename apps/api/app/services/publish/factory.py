"""微信公众号发布器工厂。

由环境变量 WECHAT_PUBLISHER 切换 mock（本地 HTML 预览）/ real（真实 API）。
"""

from app.config import settings
from app.services.publish.base import WeChatPublisher
from app.services.publish.mock import MockWeChatPublisher, RealWeChatPublisher


def get_wechat_publisher() -> WeChatPublisher:
    if settings.WECHAT_PUBLISHER == "real":
        return RealWeChatPublisher()
    return MockWeChatPublisher()
