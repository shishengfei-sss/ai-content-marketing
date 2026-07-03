from app.config import settings
from app.services.publish.base import WeChatPublisher
from app.services.publish.mock import MockWeChatPublisher, RealWeChatPublisher


def get_wechat_publisher() -> WeChatPublisher:
    if settings.WECHAT_PUBLISHER == "real":
        return RealWeChatPublisher()
    return MockWeChatPublisher()
