from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")
    password: str = Field(min_length=8, max_length=128)
    industry_code: str = "finance"
    display_name: str = ""


class LoginRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=20)
    password: str


class SmsSendRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")


class SmsSendResponse(BaseModel):
    message: str = "验证码已发送"
    mock_hint: str | None = None


class SmsLoginRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")
    code: str = Field(min_length=4, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TenantOut(BaseModel):
    id: UUID
    name: str
    industry_code: str

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: UUID
    phone: str | None = None
    email: EmailStr | None = None
    display_name: str
    role: str
    is_active: bool = True
    tenant: TenantOut

    model_config = {"from_attributes": True}


class LLMSettingsOut(BaseModel):
    provider: str
    base_url: str
    model: str
    timeout_sec: int
    is_active: bool
    api_key_masked: str
    source: str


class LLMSettingsUpdate(BaseModel):
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    api_key: str | None = None
    model: str = "deepseek-chat"
    timeout_sec: int = 60
    is_active: bool = True


class LLMTestResponse(BaseModel):
    success: bool
    model: str
    provider: str
    latency_ms: int
    message: str = ""


class ContentGenerateRequest(BaseModel):
    industry_code: str = "finance"
    platform: str = Field(pattern="^(wechat|xhs|douyin)$")
    scene: str = ""
    topic: str = Field(min_length=2, max_length=2000)
    content_format: str = Field(default="article", pattern="^(article|note|video_script)$")
    apply_user_prompt: bool = False
    ephemeral_instruction: str = ""
    selected_proposal: "ContentProposal | None" = None


class ContentProposal(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    angle: str = Field(default="", max_length=500)
    outline: str = Field(default="", max_length=2000)


class ContentProposalsRequest(BaseModel):
    industry_code: str = "finance"
    platform: str = Field(pattern="^(wechat|xhs|douyin)$")
    scene: str = ""
    topic: str = Field(min_length=2, max_length=2000)
    content_format: str = Field(default="article", pattern="^(article|note|video_script)$")
    apply_user_prompt: bool = False


class ContentProposalsResponse(BaseModel):
    proposals: list[ContentProposal]


class ContentOut(BaseModel):
    id: UUID
    platform: str
    scene: str
    topic: str
    body: str
    content_format: str = "article"
    status: str
    llm_provider: str
    llm_model: str
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    publish_error: str | None = None
    mock_read_count: int = 0
    preview_url: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    author_name: str = ""

    model_config = {"from_attributes": True}


class ContentListResponse(BaseModel):
    items: list[ContentOut]
    total: int
    page: int
    page_size: int


class ReviewActionRequest(BaseModel):
    comment: str = ""


class ScheduleRequest(BaseModel):
    scheduled_at: datetime


class CalendarEventOut(BaseModel):
    id: UUID
    title: str
    platform: str
    scheduled_at: datetime
    status: str


class DashboardStatsOut(BaseModel):
    draft_count: int
    today_scheduled: int
    reads_last_7_days: int
    generated_this_month: int
    pending_review: int = 0


class WeChatSettingsOut(BaseModel):
    bound: bool
    account_name: str
    account_type: str = "service"
    can_auto_publish: bool = False
    mode: str
    is_mock: bool


class WeChatBindRequest(BaseModel):
    account_name: str = Field(min_length=2, max_length=200)
    account_type: str = Field(default="service", pattern="^(service|subscription)$")


class TemplateOut(BaseModel):
    scene: str
    platform: str
    name: str

    model_config = {"from_attributes": True}


class KnowledgeDocumentOut(BaseModel):
    id: UUID
    title: str
    file_name: str
    scope: str
    industry_code: str = ""
    status: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeUploadTextRequest(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    text: str = Field(min_length=10, max_length=200000)
    industry_code: str = "finance"


class BrandSettingsOut(BaseModel):
    company_display_name: str
    tone: str
    cta_text: str
    sample_snippet: str

    model_config = {"from_attributes": True}


class BrandSettingsUpdate(BaseModel):
    company_display_name: str = ""
    tone: str = "专业亲切"
    cta_text: str = ""
    sample_snippet: str = ""


class UserPromptOut(BaseModel):
    global_instructions: str

    model_config = {"from_attributes": True}


class UserPromptUpdate(BaseModel):
    global_instructions: str = ""


class AnalyticsStatsOut(BaseModel):
    total_reads: int
    total_generated: int
    publish_success_rate: float
    platform_breakdown: dict[str, int]
    monthly_generation: list[dict[str, int | str]]


class ExportResponse(BaseModel):
    export_id: UUID
    export_type: str
    download_url: str
    file_name: str


class AdminUserOut(BaseModel):
    id: UUID
    phone: str | None = None
    display_name: str
    role: str
    is_active: bool
    tenant_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    display_name: str | None = None


class AdminUserResetPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class AdminContentOut(ContentOut):
    author_phone: str | None = None
    tenant_name: str = ""


class AdminContentListResponse(BaseModel):
    items: list[AdminContentOut]
    total: int
    page: int
    page_size: int


class AdminKnowledgeUploadTextRequest(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    text: str = Field(min_length=10, max_length=200000)
    industry_code: str = "finance"


class AssistantOut(BaseModel):
    code: str
    name: str
    description: str
    system_role: str
    compliance_rules: str
    disclaimer: str
    default_tone: str
    welcome_message: str
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class AssistantPublicOut(BaseModel):
    code: str
    name: str
    description: str
    welcome_message: str
    default_tone: str


class AssistantCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=2, max_length=200)
    description: str = ""
    system_role: str = Field(min_length=10, max_length=5000)
    compliance_rules: str = Field(min_length=10, max_length=8000)
    disclaimer: str = Field(min_length=4, max_length=500)
    default_tone: str = "专业亲切"
    welcome_message: str = ""
    sort_order: int = 0
    is_active: bool = True


class AssistantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    system_role: str | None = Field(default=None, min_length=10, max_length=5000)
    compliance_rules: str | None = Field(default=None, min_length=10, max_length=8000)
    disclaimer: str | None = Field(default=None, min_length=4, max_length=500)
    default_tone: str | None = None
    welcome_message: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
