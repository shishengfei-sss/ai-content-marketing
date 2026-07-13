"""AI 助手（行业包）查询与配置 — v0.6 统一为通用营销顾问。"""

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import IndustryPack

MARKETING_ADVISOR_CODE = "marketing"
LEGACY_ADVISOR_CODES = frozenset({"finance", "legal"})

DEFAULT_SYSTEM_ROLE = (
    "你是面向中小企业与营销人员的【通用营销创作顾问】，"
    "帮助用户在{platform}平台创作{format}类营销内容。"
)
DEFAULT_COMPLIANCE = """1. 内容必须合规，不得夸大承诺或误导用户
2. 必须包含免责声明（图文文末；视频脚本在最后一镜口播/字幕中体现）：{disclaimer}
3. 语气{tone}，适合目标受众阅读
4. 直接输出正文内容，不要输出 JSON 或多余解释"""
DEFAULT_DISCLAIMER = "本文仅供参考，具体以相关部门最新规定为准"
DEFAULT_WELCOME = (
    "你好！我是小营，你的 AI 营销创作顾问。直接告诉我平台与想写的主题（任意行业/题材），"
    "我会先帮您理清需求，再生成方案与正文。"
)


def normalize_advisor_code(code: str | None) -> str:
    """创作侧统一顾问 code；租户 industry_code 不参与助手选择。"""
    c = (code or "").strip()
    if not c or c in LEGACY_ADVISOR_CODES:
        return MARKETING_ADVISOR_CODE
    return c


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


def default_marketing_profile() -> AssistantProfile:
    return AssistantProfile(
        code=MARKETING_ADVISOR_CODE,
        name="小营 · 营销创作顾问",
        description="通用营销创作顾问，支持任意题材与多平台内容生成",
        system_role=DEFAULT_SYSTEM_ROLE,
        compliance_rules=DEFAULT_COMPLIANCE,
        disclaimer=DEFAULT_DISCLAIMER,
        default_tone="专业亲切",
        welcome_message=DEFAULT_WELCOME,
    )


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


def get_assistant_by_code(db: Session, code: str, *, active_only: bool = True) -> IndustryPack | None:
    query = db.query(IndustryPack).filter(IndustryPack.code == code)
    if active_only:
        query = query.filter(IndustryPack.is_active.is_(True))
    return query.first()


def get_marketing_advisor(db: Session) -> IndustryPack:
    pack = get_assistant_by_code(db, MARKETING_ADVISOR_CODE, active_only=True)
    if pack:
        return pack
    pack = get_assistant_by_code(db, MARKETING_ADVISOR_CODE, active_only=False)
    if pack:
        return pack
    raise HTTPException(status_code=500, detail="营销顾问配置未初始化，请执行 alembic upgrade head")


def get_marketing_profile(db: Session) -> AssistantProfile:
    return to_profile(get_marketing_advisor(db))


def list_active_assistants(db: Session) -> list[IndustryPack]:
    """创作页仅暴露单一营销顾问。"""
    pack = get_assistant_by_code(db, MARKETING_ADVISOR_CODE, active_only=True)
    return [pack] if pack else []


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


def require_active_assistant(db: Session, code: str) -> IndustryPack:
    normalized = normalize_advisor_code(code)
    pack = get_assistant_by_code(db, normalized, active_only=True)
    if not pack:
        if normalized == MARKETING_ADVISOR_CODE:
            raise HTTPException(status_code=500, detail="营销顾问配置未初始化，请执行 alembic upgrade head")
        raise HTTPException(status_code=400, detail="AI 助手不存在或已下架")
    return pack


def get_profile(db: Session, code: str) -> AssistantProfile:
    return to_profile(require_active_assistant(db, normalize_advisor_code(code)))
