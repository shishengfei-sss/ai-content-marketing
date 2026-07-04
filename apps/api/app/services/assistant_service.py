"""AI 助手（行业包）查询与配置。"""

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import IndustryPack

DEFAULT_SYSTEM_ROLE = "你是一名专业的营销内容创作助手，撰写{platform}{format}。"
DEFAULT_COMPLIANCE = """1. 内容必须合规，不得夸大承诺或误导用户
2. 必须包含免责声明（图文文末；视频脚本在最后一镜口播/字幕中体现）：{disclaimer}
3. 语气{tone}，适合目标受众阅读
4. 直接输出正文内容，不要输出 JSON 或多余解释"""
DEFAULT_DISCLAIMER = "本文仅供参考，具体以相关部门最新规定为准"
DEFAULT_WELCOME = (
    "您好，我是{assistant_name}。直接告诉我您想创作什么，或点击下方快捷选题开始。"
)


@dataclass
class AssistantProfile:
    code: str
    name: str
    description: str
    system_role: str
    compliance_rules: str
    disclaimer: str
    default_tone: str
    welcome_message: str


def to_profile(pack: IndustryPack) -> AssistantProfile:
    tone = pack.default_tone or "专业亲切"
    disclaimer = pack.disclaimer or DEFAULT_DISCLAIMER
    welcome = pack.welcome_message or DEFAULT_WELCOME
    return AssistantProfile(
        code=pack.code,
        name=pack.name,
        description=pack.description or "",
        system_role=pack.system_role or DEFAULT_SYSTEM_ROLE,
        compliance_rules=pack.compliance_rules or DEFAULT_COMPLIANCE,
        disclaimer=disclaimer,
        default_tone=tone,
        welcome_message=welcome.replace("{assistant_name}", pack.name),
    )


def list_active_assistants(db: Session) -> list[IndustryPack]:
    return (
        db.query(IndustryPack)
        .filter(IndustryPack.is_active.is_(True))
        .order_by(IndustryPack.sort_order.asc(), IndustryPack.name.asc())
        .all()
    )


def list_all_assistants(
    db: Session,
    *,
    q: str | None = None,
    is_active: bool | None = None,
) -> list[IndustryPack]:
    query = db.query(IndustryPack)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                IndustryPack.code.ilike(like),
                IndustryPack.name.ilike(like),
                IndustryPack.description.ilike(like),
            )
        )
    if is_active is not None:
        query = query.filter(IndustryPack.is_active.is_(is_active))
    return query.order_by(IndustryPack.sort_order.asc(), IndustryPack.name.asc()).all()


def get_assistant_by_code(db: Session, code: str, *, active_only: bool = True) -> IndustryPack | None:
    query = db.query(IndustryPack).filter(IndustryPack.code == code)
    if active_only:
        query = query.filter(IndustryPack.is_active.is_(True))
    return query.first()


def require_active_assistant(db: Session, code: str) -> IndustryPack:
    pack = get_assistant_by_code(db, code, active_only=True)
    if not pack:
        raise HTTPException(status_code=400, detail="AI 助手不存在或已下架")
    return pack


def get_profile(db: Session, code: str) -> AssistantProfile:
    return to_profile(require_active_assistant(db, code))
