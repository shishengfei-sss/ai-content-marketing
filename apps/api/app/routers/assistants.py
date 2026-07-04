from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AssistantPublicOut
from app.services.assistant_service import list_active_assistants, to_profile

router = APIRouter(prefix="/assistants", tags=["assistants"])


@router.get("", response_model=list[AssistantPublicOut])
def list_assistants(db: Session = Depends(get_db)):
    packs = list_active_assistants(db)
    return [
        AssistantPublicOut(
            code=p.code,
            name=p.name,
            description=p.description or "",
            welcome_message=to_profile(p).welcome_message,
            default_tone=p.default_tone or "专业亲切",
        )
        for p in packs
    ]
