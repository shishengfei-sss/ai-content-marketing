from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import TemplateOut
from app.services.knowledge_service import list_templates

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
def get_templates(
    industry_code: str = Query(default="marketing"),
    platform: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = list_templates(db, industry_code, platform)
    return [
        TemplateOut(
            scene=t.scene,
            platform=t.platform,
            name=t.name,
            prompt_hint=t.prompt_hint or "",
        )
        for t in items
    ]
