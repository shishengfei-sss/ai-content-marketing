from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")
    password: str = Field(min_length=8, max_length=128)
    tenant_name: str = Field(min_length=2, max_length=200)
    industry_code: str = "finance"
    display_name: str = ""

    @field_validator("tenant_name")
    @classmethod
    def strip_tenant_name(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 2:
            raise ValueError("公司名称至少 2 个字符")
        return stripped


class ForgotPasswordSendRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")


class ForgotPasswordResetRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")
    code: str = Field(min_length=4, max_length=6)
    password: str = Field(min_length=8, max_length=128)


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
    need_select_tenant: bool = False


class TenantBriefOut(BaseModel):
    id: UUID
    name: str
    industry_code: str
    role_code: str
    role_name: str

    model_config = {"from_attributes": True}


class TenantOut(BaseModel):
    id: UUID
    name: str
    industry_code: str

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    id: UUID
    phone: str | None = None
    display_name: str
    role: str
    is_active: bool = True
    active_tenant: TenantOut | None = None
    permissions: list[str] = []
    tenants: list[TenantBriefOut] = []
    need_select_tenant: bool = False


class SelectTenantRequest(BaseModel):
    tenant_id: UUID


class TenantProfileOut(BaseModel):
    id: UUID
    name: str
    industry_code: str
    credit_code: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class TenantProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    industry_code: str | None = None
    credit_code: str | None = Field(default=None, max_length=18)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if len(stripped) < 2:
            raise ValueError("公司名称至少 2 个字符")
        return stripped


class RoleOut(BaseModel):
    id: UUID
    code: str
    name: str
    is_system: bool
    permissions: list[str]

    model_config = {"from_attributes": True}


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    permissions: list[str] | None = None


class MemberOut(BaseModel):
    id: UUID
    user_id: UUID
    phone: str | None = None
    display_name: str
    role_id: UUID
    role_code: str
    role_name: str
    is_active: bool
    joined_at: datetime | None = None


class MemberCreateRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")
    display_name: str = ""
    password: str = Field(default="ChangeMe123", min_length=8, max_length=128)


class MemberRoleUpdateRequest(BaseModel):
    role_id: UUID


class UserOut(BaseModel):
    id: UUID
    phone: str | None = None
    email: EmailStr | None = None
    display_name: str
    role: str
    is_active: bool = True
    tenant: TenantOut | None = None

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


class LLMQuotaOut(BaseModel):
    used_count: int
    quota_limit: int
    remaining: int
    has_tenant_key: bool
    platform_available: bool
    default_free_quota: int = 100


class PlatformLLMSettingsOut(BaseModel):
    provider: str
    base_url: str
    model: str
    timeout_sec: int
    default_free_quota: int
    is_active: bool
    api_key_masked: str


class PlatformLLMSettingsUpdate(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout_sec: int | None = Field(default=None, ge=10, le=300)
    default_free_quota: int | None = Field(default=None, ge=1, le=100000)
    is_active: bool | None = None


class PlatformLLMTestRequest(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout_sec: int | None = Field(default=None, ge=10, le=300)


class ContentGenerateRequest(BaseModel):
    industry_code: str = "finance"
    platform: str = Field(pattern="^(wechat|xhs|douyin)$")
    scene: str = ""
    topic: str = Field(min_length=2, max_length=2000)
    content_format: str = Field(default="article", pattern="^(article|note|video_script)$")
    apply_user_prompt: bool = False
    ephemeral_instruction: str = ""
    selected_proposal: "ContentProposal | None" = None
    llm_source: str = Field(default="platform", pattern="^(platform|tenant)$")


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
    llm_source: str = Field(default="platform", pattern="^(platform|tenant)$")


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
    memberships: list["AdminMembershipBrief"] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminMembershipBrief(BaseModel):
    tenant_id: UUID
    tenant_name: str
    role_code: str
    role_name: str
    is_active: bool


class AdminTenantAdminSummary(BaseModel):
    user_id: UUID
    phone: str | None = None
    display_name: str


class AdminTenantOut(BaseModel):
    id: UUID
    name: str
    credit_code: str | None = None
    industry_code: str
    member_count: int
    admin_summaries: list[AdminTenantAdminSummary]
    quota_used: int
    quota_limit: int
    created_at: datetime


class AdminTenantListResponse(BaseModel):
    items: list[AdminTenantOut]
    total: int
    page: int
    page_size: int


class AdminTenantMemberOut(BaseModel):
    membership_id: UUID
    user_id: UUID
    phone: str | None = None
    display_name: str
    role_code: str
    role_name: str
    membership_active: bool
    user_active: bool
    joined_at: datetime


class AdminTransferAdminRequest(BaseModel):
    new_admin_user_id: UUID


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


class AgentSessionCreate(BaseModel):
    industry_code: str = "finance"
    title: str = ""


class AgentSessionOut(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    industry_code: str
    title: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentMessageCreate(BaseModel):
    role: str = Field(pattern=r"^(user|assistant|system|tool)$")
    content: str = ""
    message_type: str = "text"
    metadata: dict | None = None


class AgentMessageOut(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    message_type: str
    metadata_json: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    llm_source: str = Field(default="platform", pattern="^(platform|tenant)$")
    selected_proposal_index: int | None = Field(default=None, ge=0, le=20)
    mode: str = Field(default="legacy", pattern="^(legacy|react)$")


class AgentChatResponse(BaseModel):
    action: str
    assistant_message: str
    clarify_question: str | None = None
    proposals: list[ContentProposal] | None = None
    content: ContentOut | None = None
    message_id: UUID


class AgentToolOut(BaseModel):
    name: str
    description: str
    parameters: dict
    required_permissions: list[str] = Field(default_factory=list)


class AgentToolExecuteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    arguments: dict = Field(default_factory=dict)
    industry_code: str = "finance"


class AgentMemoryCreate(BaseModel):
    scope: str = Field(pattern=r"^(user|tenant)$")
    fact_text: str = Field(min_length=1, max_length=4000)
    category: str = Field(default="preference", max_length=50)
    source: str = Field(default="explicit", pattern=r"^(explicit|inferred)$")
    is_confirmed: bool = True


class AgentMemoryUpdate(BaseModel):
    fact_text: str | None = Field(default=None, min_length=1, max_length=4000)
    category: str | None = Field(default=None, max_length=50)
    is_confirmed: bool | None = None


class AgentMemoryOut(BaseModel):
    id: UUID
    scope: str
    user_id: UUID | None = None
    tenant_id: UUID | None = None
    category: str
    fact_text: str
    source: str
    is_confirmed: bool
    created_by: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentSessionSummaryOut(BaseModel):
    id: UUID
    session_id: UUID
    tenant_id: UUID
    user_id: UUID
    summary_text: str
    topics_json: str | None = None
    message_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentRecallResponse(BaseModel):
    query: str
    session_summaries: list[AgentSessionSummaryOut]
    memory_facts: list[AgentMemoryOut]
    mode: str = "keyword"


class AgentMemoryContextOut(BaseModel):
    context: str
    char_count: int
    max_chars: int


class AgentWorkflowCreate(BaseModel):
    pipeline_code: str = Field(min_length=1, max_length=50)
    input: dict = Field(default_factory=dict)
    session_id: UUID | None = None
    auto_run: bool = True


class AgentWorkflowStepOut(BaseModel):
    id: UUID
    step_index: int
    step_code: str
    tool_name: str
    agent_code: str = "creator"
    status: str
    input_json: str | None = None
    output_json: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentWorkflowOut(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    session_id: UUID | None = None
    pipeline_code: str
    status: str
    current_step: int
    input_json: str
    output_json: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    steps: list[AgentWorkflowStepOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AgentComplianceCheckRequest(BaseModel):
    content_id: UUID
    workflow_id: UUID | None = None
    llm_source: str = "platform"


class AgentComplianceIssueOut(BaseModel):
    code: str
    severity: str
    message: str


class AgentComplianceReportOut(BaseModel):
    report_id: UUID
    content_id: UUID
    status: str
    issues: list[AgentComplianceIssueOut] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    workflow_id: UUID | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentPendingActionOut(BaseModel):
    action_id: UUID
    action_type: str
    status: str
    content_id: UUID
    summary: str
    payload: dict = Field(default_factory=dict)
    created_at: datetime | None = None


class AgentOpsConfirmOut(BaseModel):
    action_id: UUID
    action_type: str
    status: str
    content_id: UUID
    scheduled_at: datetime | None = None


class AgentSeoOptimizeRequest(BaseModel):
    content_id: UUID
    llm_source: str = "platform"


class AgentSeoOptimizeOut(BaseModel):
    content_id: UUID
    platform: str
    title_candidates: list[str]
    tags: list[str]
