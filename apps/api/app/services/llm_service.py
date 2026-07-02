from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import LLMConfig
from app.services.crypto import decrypt_api_key
from app.services.llm.base import LLMMessage, LLMResponse
from app.services.llm.factory import get_provider


@dataclass
class ResolvedLLMConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    timeout_sec: int
    source: str  # tenant | env


class LLMService:
    def resolve_config(self, db: Session, tenant_id: UUID) -> ResolvedLLMConfig:
        row = db.query(LLMConfig).filter(
            LLMConfig.tenant_id == tenant_id, LLMConfig.is_active.is_(True)
        ).first()

        if row and row.api_key_encrypted:
            return ResolvedLLMConfig(
                provider=row.provider,
                base_url=row.base_url,
                api_key=decrypt_api_key(row.api_key_encrypted),
                model=row.model,
                timeout_sec=row.timeout_sec,
                source="tenant",
            )

        provider = settings.LLM_PROVIDER
        if provider == "deepseek":
            return ResolvedLLMConfig(
                provider="deepseek",
                base_url=settings.DEEPSEEK_BASE_URL,
                api_key=settings.DEEPSEEK_API_KEY,
                model=settings.DEEPSEEK_MODEL,
                timeout_sec=settings.LLM_TIMEOUT_SEC,
                source="env",
            )

        return ResolvedLLMConfig(
            provider="openai_compatible",
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            timeout_sec=settings.LLM_TIMEOUT_SEC,
            source="env",
        )

    async def chat(
        self,
        db: Session,
        tenant_id: UUID,
        messages: list[LLMMessage],
    ) -> LLMResponse:
        cfg = self.resolve_config(db, tenant_id)
        if not cfg.api_key:
            raise ValueError("LLM_API_KEY_NOT_CONFIGURED")

        provider = get_provider(cfg.provider)
        result = await provider.chat(
            messages,
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout_sec=cfg.timeout_sec,
        )
        return LLMResponse(content=result.content, model=cfg.model, provider=cfg.provider)


llm_service = LLMService()
