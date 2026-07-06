from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_active_tenant_id
from app.models import User
from app.schemas import BrandSettingsOut, BrandSettingsUpdate, UserPromptOut, UserPromptUpdate
from app.services.brand_service import get_or_create_brand, get_or_create_user_prompt, update_brand, update_user_prompt

router = APIRouter(prefix="/settings", tags=["brand-settings"])


@router.get("/brand", response_model=BrandSettingsOut)
def get_brand(
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    profile = get_or_create_brand(db, tenant_id)
    return profile


@router.put("/brand", response_model=BrandSettingsOut)
def put_brand(
    body: BrandSettingsUpdate,
    tenant_id: UUID = Depends(require_active_tenant_id),
    db: Session = Depends(get_db),
):
    return update_brand(
        db,
        tenant_id,
        company_display_name=body.company_display_name,
        tone=body.tone,
        cta_text=body.cta_text,
        sample_snippet=body.sample_snippet,
    )


@router.get("/user-prompt", response_model=UserPromptOut)
def get_user_prompt_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_or_create_user_prompt(db, current_user)


@router.put("/user-prompt", response_model=UserPromptOut)
def put_user_prompt_settings(
    body: UserPromptUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return update_user_prompt(db, current_user, body.global_instructions)
