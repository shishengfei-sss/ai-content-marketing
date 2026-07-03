from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    industry_code: str = "finance"
    display_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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
    email: EmailStr
    display_name: str
    role: str
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
    apply_user_prompt: bool = False
    ephemeral_instruction: str = ""


class ContentOut(BaseModel):
    id: UUID
    platform: str
    scene: str
    topic: str
    body: str
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
    pending_review: int
    today_scheduled: int
    reads_last_7_days: int
    generated_this_month: int


class WeChatSettingsOut(BaseModel):
    bound: bool
    account_name: str
    mode: str
    is_mock: bool


class WeChatBindRequest(BaseModel):
    account_name: str = Field(min_length=2, max_length=200)


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
