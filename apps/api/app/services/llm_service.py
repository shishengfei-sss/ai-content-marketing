"""LLM 业务统一入口。

配置来源：
- llm_source=platform：平台 Key + 免费额度（正文生成成功扣 1 次）
- llm_source=tenant：租户自有 Key，不扣平台额度
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import LLMConfig
from app.services.crypto import decrypt_api_key
from app.services.llm.base import LLMMessage, LLMResponse
from app.services.llm.factory import get_provider
from app.services.platform_llm_service import (
    ensure_platform_quota_available,
    get_platform_config,
    normalize_platform_provider,
    resolve_platform_api_key,
)

logger = logging.getLogger(__name__)


@dataclass
class ResolvedLLMConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    timeout_sec: int
    source: str  # platform | tenant


class LLMService:
    def resolve_config(
        self,
        db: Session,
        tenant_id: UUID,
        llm_source: str = "platform",
    ) -> ResolvedLLMConfig:
        source = (llm_source or "platform").strip().lower()
        if source == "tenant":
            row = (
                db.query(LLMConfig)
                .filter(
                    LLMConfig.tenant_id == tenant_id,
                    LLMConfig.is_active.is_(True),
                )
                .first()
            )
            if not row or not row.api_key_encrypted:
                raise ValueError("LLM_TENANT_KEY_NOT_CONFIGURED")
            return ResolvedLLMConfig(
                provider=row.provider,
                base_url=row.base_url,
                api_key=decrypt_api_key(row.api_key_encrypted),
                model=row.model,
                timeout_sec=row.timeout_sec,
                source="tenant",
            )

        if source == "platform":
            platform = get_platform_config(db)
            if not platform or not platform.is_active:
                raise ValueError("LLM_PLATFORM_NOT_CONFIGURED")

            # 仅 CI / 离线验收显式开启时允许 Fake；避免测试残留导致创作页一直套模板
            force_fake = os.environ.get("FORCE_FAKE_PLATFORM_LLM") == "1"
            is_fake = platform.provider == "fake" or platform.base_url == "http://fake.local"
            if is_fake and force_fake:
                return ResolvedLLMConfig(
                    provider="fake",
                    base_url=platform.base_url or "http://fake.local",
                    api_key="fake-key",
                    model=platform.model or "fake-model",
                    timeout_sec=platform.timeout_sec,
                    source="platform",
                )
            if is_fake and not force_fake:
                logger.warning(
                    "platform LLM is fake but FORCE_FAKE_PLATFORM_LLM!=1; "
                    "falling back to deepseek to avoid stub proposals in product UI"
                )

            provider_name = normalize_platform_provider(
                "deepseek" if is_fake else platform.provider
            )
            base_url = (
                "https://api.deepseek.com"
                if is_fake
                else (platform.base_url or "https://api.deepseek.com")
            )
            model = "deepseek-v4-flash" if is_fake else platform.model
            if not is_fake and provider_name == "deepseek":
                from app.services.platform_llm_service import normalize_deepseek_model

                model = normalize_deepseek_model(model)
            api_key = resolve_platform_api_key(platform)
            if not api_key:
                raise ValueError("LLM_PLATFORM_NOT_CONFIGURED")
            return ResolvedLLMConfig(
                provider=provider_name,
                base_url=base_url,
                api_key=api_key,
                model=model,
                timeout_sec=platform.timeout_sec,
                source="platform",
            )

        raise ValueError("INVALID_LLM_SOURCE")

    async def chat(
        self,
        db: Session,
        tenant_id: UUID,
        messages: list[LLMMessage],
        llm_source: str = "platform",
        *,
        check_platform_quota: bool = False,
    ) -> LLMResponse:
        if check_platform_quota and (llm_source or "platform").strip().lower() == "platform":
            ensure_platform_quota_available(db, tenant_id)

        cfg = self.resolve_config(db, tenant_id, llm_source)
        provider = get_provider(cfg.provider)
        result = await provider.chat(
            messages,
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout_sec=cfg.timeout_sec,
        )
        return LLMResponse(content=result.content, model=cfg.model, provider=cfg.provider)

    async def stream(
        self,
        db: Session,
        tenant_id: UUID,
        messages: list[LLMMessage],
        llm_source: str = "platform",
        *,
        check_platform_quota: bool = False,
    ):
        if check_platform_quota and (llm_source or "platform").strip().lower() == "platform":
            ensure_platform_quota_available(db, tenant_id)

        cfg = self.resolve_config(db, tenant_id, llm_source)
        provider = get_provider(cfg.provider)
        async for chunk in provider.stream(
            messages,
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout_sec=cfg.timeout_sec,
        ):
            yield chunk


llm_service = LLMService()
