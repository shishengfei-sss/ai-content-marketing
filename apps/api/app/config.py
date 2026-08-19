from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "sqlite:///./dev.db"
    JWT_SECRET: str = "dev-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7

    LLM_ENCRYPTION_KEY: str = "dev-32-byte-key-change-in-prod!!"

    LLM_PROVIDER: str = "deepseek"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"

    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    LLM_TIMEOUT_SEC: int = 60

    WECHAT_PUBLISHER: str = "mock"
    STORAGE_DIR: str = "./storage"
    ATTACHMENT_DIR: str = "./storage/attachments"
    PUBLISH_POLL_SEC: int = 30
    CRM_RECLAIM_POLL_SEC: int = 300
    CRM_CONTRACT_EXPIRY_POLL_SEC: int = 3600
    CRM_QUOTE_EXPIRY_POLL_SEC: int = 3600
    SHOP_BOOKING_EXPIRE_POLL_SEC: int = 900

    CORS_ORIGINS: str = (
        "http://127.0.0.1:5173,http://localhost:5173,"
        "http://127.0.0.1:5174,http://localhost:5174,"
        "http://127.0.0.1:5175,http://localhost:5175,"
        "http://127.0.0.1:5176,http://localhost:5176,"
        "http://127.0.0.1:5177,http://localhost:5177"
    )

    SMS_PROVIDER: str = "mock"
    SMS_MOCK_CODE: str = "1111"
    SMS_CODE_EXPIRE_SEC: int = 300
    SMS_SEND_INTERVAL_SEC: int = 60

    # 公域映射：Phase1 本地/联调提交后自动模拟外部审核通过
    SHOP_CHANNEL_MOCK_AUDIT: str = "1"
    # 本地演示：模拟抖店单后拼领权 H5 链接
    SHOP_H5_DEMO_BASE: str = "http://localhost:5174"

    # 微信支付：stub | production（真机依赖 B-M3）
    WECHAT_PAY_MODE: str = "stub"
    WECHAT_PAY_MOCK: str = "1"
    WECHAT_PAY_MOCK_BASE_URL: str = "http://mock.wechat-pay.local"
    WECHAT_PAY_APPID: str = ""
    WECHAT_PAY_MCHID: str = ""
    WECHAT_PAY_API_KEY: str = ""

    @property
    def storage_published_dir(self) -> Path:
        return Path(self.STORAGE_DIR) / "published"


settings = Settings()
