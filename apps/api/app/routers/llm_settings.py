import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import LLMConfig, User
from app.schemas import LLMSettingsOut, LLMSettingsUpdate, LLMTestResponse
from app.services.crypto import decrypt_api_key, encrypt_api_key, mask_api_key
from app.services.llm.base import LLMMessage
from app.services.llm.factory import get_provider
from app.services.llm_service import llm_service

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


@router.get("", response_model=LLMSettingsOut)
def get_llm_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(LLMConfig).filter(LLMConfig.tenant_id == current_user.tenant_id).first()
    if row:
        key = decrypt_api_key(row.api_key_encrypted) if row.api_key_encrypted else ""
        return _to_out(row, "tenant", mask_api_key(key))

    resolved = llm_service.resolve_config(db, current_user.tenant_id)
    return LLMSettingsOut(
        provider=resolved.provider,
        base_url=resolved.base_url,
        model=resolved.model,
        timeout_sec=resolved.timeout_sec,
        is_active=True,
        api_key_masked=mask_api_key(resolved.api_key),
        source=resolved.source,
    )


@router.put("", response_model=LLMSettingsOut)
def update_llm_settings(
    body: LLMSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(LLMConfig).filter(LLMConfig.tenant_id == current_user.tenant_id).first()
    if not row:
        row = LLMConfig(tenant_id=current_user.tenant_id)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resolved = llm_service.resolve_config(db, current_user.tenant_id)
    if not resolved.api_key:
        raise HTTPException(status_code=400, detail="请先配置 API Key")

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
