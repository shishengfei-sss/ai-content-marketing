"""租户品牌与用户个人提示词。

品牌信息（公司名、语气、CTA、范文）注入生成 Prompt；
个人提示词仅在请求 apply_user_prompt=true 时生效。
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import TenantBrandProfile, User, UserPromptProfile


def get_or_create_brand(db: Session, tenant_id: UUID) -> TenantBrandProfile:
    profile = db.query(TenantBrandProfile).filter(TenantBrandProfile.tenant_id == tenant_id).first()
    if profile:
        return profile
    profile = TenantBrandProfile(tenant_id=tenant_id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_brand(
    db: Session,
    tenant_id: UUID,
    *,
    company_display_name: str,
    tone: str,
    cta_text: str,
    sample_snippet: str,
) -> TenantBrandProfile:
    profile = get_or_create_brand(db, tenant_id)
    profile.company_display_name = company_display_name
    profile.tone = tone
    profile.cta_text = cta_text
    profile.sample_snippet = sample_snippet
    db.commit()
    db.refresh(profile)
    return profile


def get_or_create_user_prompt(db: Session, user: User) -> UserPromptProfile:
    profile = db.query(UserPromptProfile).filter(UserPromptProfile.user_id == user.id).first()
    if profile:
        return profile
    profile = UserPromptProfile(user_id=user.id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_user_prompt(db: Session, user: User, global_instructions: str) -> UserPromptProfile:
    profile = get_or_create_user_prompt(db, user)
    profile.global_instructions = global_instructions
    db.commit()
    db.refresh(profile)
    return profile
