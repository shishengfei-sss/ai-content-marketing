"""平台 LLM 配置与租户免费额度。"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import LLMConfig, PlatformLLMConfig, TenantLLMUsage
from app.services.crypto import decrypt_api_key


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
    platform_ready = bool(
        platform
        and platform.is_active
        and (platform.api_key_encrypted or settings.DEEPSEEK_API_KEY or settings.LLM_API_KEY)
    )
    return {
        "used_count": usage.used_count,
        "quota_limit": limit,
        "remaining": remaining,
        "has_tenant_key": tenant_has_own_key(db, tenant_id),
        "platform_available": platform_ready,
        "default_free_quota": platform.default_free_quota if platform else 100,
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
        return decrypt_api_key(platform.api_key_encrypted)
    if settings.DEEPSEEK_API_KEY:
        return settings.DEEPSEEK_API_KEY
    return settings.LLM_API_KEY or ""
