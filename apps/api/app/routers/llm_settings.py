import time
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_active_tenant_id
from app.models import LLMConfig
from app.schemas import LLMQuotaOut, LLMSettingsOut, LLMSettingsUpdate, LLMTestResponse
from app.services.crypto import decrypt_api_key, encrypt_api_key, mask_api_key
from app.services.llm.base import LLMMessage
from app.services.llm.factory import get_provider
from app.services.llm_service import llm_service
from app.services.platform_llm_service import get_quota_status

router = APIRouter(prefix="/settings/llm", tags=["llm-settings"])


def _to_out(cfg, source: str, masked_key: str) -> LLMSettingsOut:
    return LLMSettingsOut(
        provider=cfg.provider,
        base_url=cfg.base_url,
        model=cfg.model,
        timeout_sec=cfg.timeout_sec,
        is_active=getattr(cfg, "is_active", True),
        api_key_masked=masked_key,
        source=source,
    )


@router.get("/quota", response_model=LLMQuotaOut)
def get_llm_quota(
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    return LLMQuotaOut(**get_quota_status(db, tenant_id))


@router.get("", response_model=LLMSettingsOut)
def get_llm_settings(
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    row = db.query(LLMConfig).filter(LLMConfig.tenant_id == tenant_id).first()
    if row:
        key = decrypt_api_key(row.api_key_encrypted) if row.api_key_encrypted else ""
        return _to_out(row, "tenant", mask_api_key(key))

    return LLMSettingsOut(
        provider="deepseek",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        timeout_sec=60,
        is_active=True,
        api_key_masked="",
        source="none",
    )


@router.put("", response_model=LLMSettingsOut)
def update_llm_settings(
    body: LLMSettingsUpdate,
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    row = db.query(LLMConfig).filter(LLMConfig.tenant_id == tenant_id).first()
    if not row:
        row = LLMConfig(tenant_id=tenant_id)
        db.add(row)

    row.provider = body.provider
    row.base_url = body.base_url
    row.model = body.model
    row.timeout_sec = body.timeout_sec
    row.is_active = body.is_active
    if body.api_key:
        row.api_key_encrypted = encrypt_api_key(body.api_key)

    db.commit()
    db.refresh(row)

    key = decrypt_api_key(row.api_key_encrypted) if row.api_key_encrypted else ""
    return _to_out(row, "tenant", mask_api_key(key))


@router.post("/test", response_model=LLMTestResponse)
async def test_llm_settings(
    llm_source: str = Query(default="tenant", pattern="^(platform|tenant)$"),
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    try:
        resolved = llm_service.resolve_config(db, tenant_id, llm_source)
    except ValueError as e:
        code = str(e)
        if code == "LLM_TENANT_KEY_NOT_CONFIGURED":
            raise HTTPException(status_code=400, detail="请先配置我的 API Key") from e
        raise HTTPException(status_code=400, detail="平台 AI 未配置") from e

    provider = get_provider(resolved.provider)
    started = time.perf_counter()
    try:
        result = await provider.chat(
            [LLMMessage(role="user", content="请回复：连接成功")],
            model=resolved.model,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
            timeout_sec=min(resolved.timeout_sec, 30),
        )
        latency = int((time.perf_counter() - started) * 1000)
        return LLMTestResponse(
            success=True,
            model=result.model,
            provider=resolved.provider,
            latency_ms=latency,
            message=result.content[:200],
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"模型连接失败: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"模型连接失败: {e}") from e
