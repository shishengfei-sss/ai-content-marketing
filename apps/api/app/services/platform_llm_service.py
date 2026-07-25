"""平台 LLM 配置与租户免费额度。"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import LLMConfig, PlatformLLMConfig, TenantLLMUsage
from app.services.crypto import decrypt_api_key

REAL_PLATFORM_PROVIDERS = frozenset({"deepseek", "openai_compatible", "dashscope"})

_DEEPSEEK_MODEL_ALIASES = {
    "deepseek-v4-flash": "deepseek-v4-flash",
    "deepseek-v4-pro": "deepseek-v4-pro",
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-flash",
    "deepseek-v3-flash": "deepseek-v4-flash",
}


def normalize_deepseek_model(model: str | None) -> str:
    """DeepSeek model id 大小写敏感；纠正常见错误写法。"""
    raw = (model or "").strip()
    if not raw:
        return "deepseek-v4-flash"
    if raw in _DEEPSEEK_MODEL_ALIASES:
        return _DEEPSEEK_MODEL_ALIASES[raw]
    lowered = raw.lower()
    if lowered in _DEEPSEEK_MODEL_ALIASES:
        return _DEEPSEEK_MODEL_ALIASES[lowered]
    # DeepSeek-V4-Flash / DeepSeek_V4_Flash 等
    compact = lowered.replace("_", "-")
    if compact in _DEEPSEEK_MODEL_ALIASES:
        return _DEEPSEEK_MODEL_ALIASES[compact]
    return raw


def normalize_platform_provider(provider: str | None) -> str:
    name = (provider or "deepseek").strip().lower()
    if name == "fake" or name not in REAL_PLATFORM_PROVIDERS:
        return "deepseek"
    return name


def get_platform_config(db: Session) -> PlatformLLMConfig | None:
    return db.query(PlatformLLMConfig).order_by(PlatformLLMConfig.updated_at.desc()).first()


def tenant_has_own_key(db: Session, tenant_id: UUID) -> bool:
    row = (
        db.query(LLMConfig)
        .filter(
            LLMConfig.tenant_id == tenant_id,
            LLMConfig.is_active.is_(True),
        )
        .first()
    )
    return bool(row and row.api_key_encrypted)


def get_or_create_usage(db: Session, tenant_id: UUID) -> TenantLLMUsage:
    usage = db.query(TenantLLMUsage).filter(TenantLLMUsage.tenant_id == tenant_id).first()
    if usage:
        return usage
    usage = TenantLLMUsage(tenant_id=tenant_id, used_count=0)
    db.add(usage)
    db.flush()
    return usage


def resolve_quota_limit(db: Session, usage: TenantLLMUsage) -> int:
    if usage.quota_limit is not None:
        return usage.quota_limit
    platform = get_platform_config(db)
    if platform:
        return platform.default_free_quota
    return 100


def get_quota_status(db: Session, tenant_id: UUID) -> dict:
    usage = get_or_create_usage(db, tenant_id)
    limit = resolve_quota_limit(db, usage)
    remaining = max(0, limit - usage.used_count)
    platform = get_platform_config(db)
    is_fake = bool(
        platform
        and (platform.provider == "fake" or platform.base_url == "http://fake.local")
    )
    has_key = bool(
        platform
        and (
            resolve_platform_api_key(platform)
            or settings.DEEPSEEK_API_KEY
            or settings.LLM_API_KEY
        )
    )
    # fake 仅 CI 可用；产品侧若残留 fake 仍视为可用（会回退 deepseek），但暴露真实模型名
    platform_ready = bool(platform and platform.is_active and (has_key or is_fake))
    if is_fake:
        provider_name, model_name = "deepseek", normalize_deepseek_model(
            settings.DEEPSEEK_MODEL or "deepseek-v4-flash"
        )
    else:
        provider_name = normalize_platform_provider(platform.provider) if platform else "deepseek"
        model_name = normalize_deepseek_model(
            platform.model if platform else (settings.DEEPSEEK_MODEL or "deepseek-v4-flash")
        )
    return {
        "used_count": usage.used_count,
        "quota_limit": limit,
        "remaining": remaining,
        "has_tenant_key": tenant_has_own_key(db, tenant_id),
        "platform_available": platform_ready,
        "default_free_quota": platform.default_free_quota if platform else 100,
        "platform_provider": provider_name,
        "platform_model": model_name,
    }


def ensure_platform_quota_available(db: Session, tenant_id: UUID) -> None:
    status = get_quota_status(db, tenant_id)
    if status["remaining"] <= 0:
        raise HTTPException(
            status_code=400,
            detail="平台免费额度已用完，请切换为「我的 API Key」或在设置中配置",
        )
    if not status["platform_available"]:
        raise HTTPException(status_code=400, detail="平台 AI 未配置，请联系管理员或使用我的 API Key")


def consume_platform_quota(db: Session, tenant_id: UUID) -> None:
    ensure_platform_quota_available(db, tenant_id)
    usage = get_or_create_usage(db, tenant_id)
    limit = resolve_quota_limit(db, usage)
    if usage.used_count >= limit:
        raise HTTPException(status_code=400, detail="平台免费额度已用完")
    usage.used_count += 1
    db.flush()


def resolve_platform_api_key(platform: PlatformLLMConfig) -> str:
    if platform.api_key_encrypted:
        key = decrypt_api_key(platform.api_key_encrypted)
        if key and key not in ("fake-key", "fake"):
            return key
    if settings.DEEPSEEK_API_KEY:
        return settings.DEEPSEEK_API_KEY
    return settings.LLM_API_KEY or ""
