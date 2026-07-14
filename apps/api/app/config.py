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
    DEEPSEEK_MODEL: str = "deepseek-chat"

    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    LLM_TIMEOUT_SEC: int = 60

    WECHAT_PUBLISHER: str = "mock"
    STORAGE_DIR: str = "./storage"
    ATTACHMENT_DIR: str = "./storage/attachments"
    PUBLISH_POLL_SEC: int = 30

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

    @property
    def storage_published_dir(self) -> Path:
        return Path(self.STORAGE_DIR) / "published"


settings = Settings()
