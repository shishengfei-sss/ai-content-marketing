"""平台商城 API Schema。"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PlatformMerchantListItem(BaseModel):
    tenant_id: UUID
    tenant_name: str
    merchant_id: UUID | None = None
    merchant_code: str | None = None
    onboarding_application_id: UUID | None = None
    display_name: str
    entity_type: str | None = None
    onboarding_status: str
    plan_label: str | None = None
    plan_status: str | None = None
    benefits_until: date | None = None
    store_count_active: int | None = None
    store_quota: int | None = None
    account_manager_user_id: UUID | None = None
    account_manager_name: str | None = None
    tags: list[str] = Field(default_factory=list)
    fee_tier: str | None = None
    has_pending_renewal: bool = False
    created_at: datetime | None = None


class PlatformMerchantListResponse(BaseModel):
    items: list[PlatformMerchantListItem]
    total: int
    page: int
    page_size: int
    scope: str = Field(description="all | assigned")


class ShopMerchantTagItem(BaseModel):
    id: UUID
    name: str
    color: str = "blue"
    usage_count: int = 0
    is_archived: bool = False
    is_common: bool = False


class PlatformPendingRenewalItem(BaseModel):
    service_log_id: UUID
    merchant_id: UUID
    tenant_id: UUID
    display_name: str
    plan_label: str | None = None
    target_plan: str | None = None
    purchase_mode: str | None = None
    quoted_amount_cents: int | None = None
    catalog_price_cents: int | None = None
    content: str
    status: str = "pending"
    status_label: str | None = None
    operator_user_id: UUID
    operator_name: str | None = None
    created_at: datetime


class PlatformPendingRenewalListResponse(BaseModel):
    items: list[PlatformPendingRenewalItem]
    total: int


class OnboardingApplicationCreate(BaseModel):
    tenant_id: UUID
    entity_type: str
    legal_name: str
    display_name: str | None = None
    contact_name: str
    contact_mobile: str
    id_no: str | None = None
    unified_social_credit_code: str | None = None
    legal_rep_name: str | None = None
    bank_account_info: dict = Field(default_factory=dict)
    qualification_files: dict = Field(default_factory=dict)
    ocr_results: list = Field(default_factory=list)
    remark: str | None = None


class MerchantSelfOnboardingCreate(BaseModel):
    """A20 商家自申：tenant 取当前 JWT，无关联租户选择。"""

    entity_type: str
    legal_name: str
    display_name: str | None = None
    contact_name: str
    contact_mobile: str
    id_no: str | None = None
    unified_social_credit_code: str | None = None
    legal_rep_name: str | None = None
    bank_account_info: dict = Field(default_factory=dict)
    qualification_files: dict = Field(default_factory=dict)
    ocr_results: list = Field(default_factory=list)
    remark: str | None = None


class MerchantOnboardingApplicationSummary(BaseModel):
    id: UUID
    application_no: str | None = None
    status: str
    entity_type: str
    legal_name: str
    display_name: str
    contact_name: str
    contact_mobile: str
    id_no: str | None = None
    unified_social_credit_code: str | None = None
    legal_rep_name: str | None = None
    reject_code: str | None = None
    reject_reason: str | None = None
    submitted_at: datetime
    bank_account_info: dict = Field(default_factory=dict)
    qualification_files: dict = Field(default_factory=dict)
    ocr_results: list = Field(default_factory=list)
    remark: str | None = None


class MerchantOnboardingStatusResponse(BaseModel):
    state: str = Field(description="not_onboarded|reviewing|rejected|onboarded")
    merchant_id: UUID | None = None
    merchant_status: str | None = None
    application: MerchantOnboardingApplicationSummary | None = None
    prefill: OnboardingPrefillResponse | None = None


class OnboardingApplicationOut(BaseModel):
    id: UUID
    application_no: str
    tenant_id: UUID
    entity_type: str
    initiator: str
    status: str
    legal_name: str
    display_name: str
    contact_name: str
    contact_mobile: str
    id_no: str | None = None
    unified_social_credit_code: str | None = None
    legal_rep_name: str | None = None
    bank_account_info: dict = Field(default_factory=dict)
    qualification_files: dict = Field(default_factory=dict)
    ocr_results: list = Field(default_factory=list)
    remark: str | None = None
    submitted_at: datetime
    created_by: UUID | None = None


class TenantOnboardingOption(BaseModel):
    tenant_id: UUID
    tenant_name: str
    credit_code: str | None = None
    legal_name_prefill: str


class TenantOnboardingSearchResponse(BaseModel):
    items: list[TenantOnboardingOption]
    total: int


class OnboardingPrefillResponse(BaseModel):
    tenant_id: UUID
    tenant_name: str
    legal_name: str
    display_name: str
    unified_social_credit_code: str | None = None


class MerchantStoreItem(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    logo_url: str | None = None
    wx_mp_app_id: str | None = None
    created_at: datetime | None = None
    product_count: int = 0
    month_gmv_cents: int = 0


class MerchantServiceLogItem(BaseModel):
    id: UUID
    type: str
    status: str
    content: str
    payload_json: dict = Field(default_factory=dict)
    operator_user_id: UUID
    operator_name: str | None = None
    follow_up_at: datetime | None = None
    related_onboarding_id: UUID | None = None
    related_subscription_id: UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class MerchantServiceLogListResponse(BaseModel):
    items: list[MerchantServiceLogItem]
    total: int
    page: int
    page_size: int


class OnboardingMaterialSection(BaseModel):
    source: str = Field(description="merchant | application")
    application_id: UUID | None = None
    application_no: str | None = None
    entity_type: str | None = None
    legal_name: str | None = None
    display_name: str | None = None
    contact_name: str | None = None
    contact_mobile: str | None = None
    id_no: str | None = None
    unified_social_credit_code: str | None = None
    legal_rep_name: str | None = None
    qualification_files: dict = Field(default_factory=dict)
    ocr_results: list = Field(default_factory=list)
    bank_account_info: dict = Field(default_factory=dict)
    bank_account_display: str | None = None
    status: str | None = None


class MerchantRevealRequest(BaseModel):
    field: str = Field(default="contact_mobile", description="contact_mobile | id_no | bank_account_no")


class MerchantRevealResponse(BaseModel):
    field: str
    value: str


class PlatformMerchantDetailResponse(BaseModel):
    tenant_id: UUID
    tenant_name: str
    merchant_id: UUID | None = None
    merchant_code: str | None = None
    onboarding_application_id: UUID | None = None
    display_name: str
    entity_type: str | None = None
    onboarding_status: str
    contact_name: str | None = None
    contact_mobile: str | None = None
    plan_label: str | None = None
    plan_status: str | None = None
    benefits_until: date | None = None
    store_count_active: int | None = None
    store_quota: int | None = None
    account_manager_user_id: UUID | None = None
    account_manager_name: str | None = None
    tags: list[str] = Field(default_factory=list)
    tag_items: list[ShopMerchantTagItem] = Field(default_factory=list)
    has_pending_renewal: bool = False
    onboarding_approved_at: datetime | None = None
    stores: list[MerchantStoreItem] = Field(default_factory=list)
    month_gmv_cents: int = 0
    onboarding_materials: OnboardingMaterialSection | None = None
    service_logs: list[MerchantServiceLogItem] = Field(default_factory=list)
    operation_logs: list[dict] = Field(default_factory=list)
    scope: str = Field(description="all | assigned")


class OnboardingApplicationListItem(BaseModel):
    id: UUID
    application_no: str
    tenant_id: UUID
    tenant_name: str
    display_name: str
    legal_name: str | None = None
    entity_type: str
    initiator: str
    status: str
    contact_name: str
    contact_mobile: str
    submitted_at: datetime
    reviewed_at: datetime | None = None
    reviewer_name: str | None = None
    merchant_id: UUID | None = None
    merchant_code: str | None = None


class OnboardingApplicationListResponse(BaseModel):
    items: list[OnboardingApplicationListItem]
    total: int
    page: int
    page_size: int


class OnboardingApplicationDetail(OnboardingApplicationOut):
    tenant_name: str
    reject_code: str | None = None
    reject_reason: str | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    merchant_id: UUID | None = None
    merchant_code: str | None = None
    bank_account_display: str | None = None
    review_logs: list["OnboardingReviewLogItem"] = Field(default_factory=list)


class OnboardingReviewLogItem(BaseModel):
    id: UUID
    action: str
    action_label: str
    summary: str
    operator_name: str | None = None
    created_at: datetime
    meta: dict = Field(default_factory=dict)


class OnboardingRejectRequest(BaseModel):
    reject_code: str = "other"
    reject_reason: str


class OnboardingRejectReasonItem(BaseModel):
    code: str
    label: str


class OnboardingRejectReasonGroup(BaseModel):
    group: str
    items: list[OnboardingRejectReasonItem]


class OnboardingRejectReasonsResponse(BaseModel):
    groups: list[OnboardingRejectReasonGroup]
    items: list[OnboardingRejectReasonItem]


class OnboardingApprovePlanOption(BaseModel):
    id: UUID
    code: str
    name: str
    allowed_entity_types: list[str] = Field(default_factory=list)


class OnboardingApproveManagerOption(BaseModel):
    id: UUID
    display_name: str
    platform_shop_role: str | None = None
    is_current: bool = False


class OnboardingApproveOptionsResponse(BaseModel):
    plans: list[OnboardingApprovePlanOption]
    managers: list[OnboardingApproveManagerOption]
    default_manager_user_id: UUID | None = None


class OnboardingApproveRequest(BaseModel):
    plan_label: str | None = None
    plan_id: UUID | None = None
    benefits_from: date | None = None
    benefits_until: date | None = None
    trial_days: int | None = Field(default=None, description="未填 benefits_until 时按天数计算")
    store_quota: int = 1
    account_manager_user_id: UUID | None = None

    @model_validator(mode="after")
    def _need_plan(self):
        if not self.plan_id and not (self.plan_label or "").strip():
            raise ValueError("首开套餐必选")
        return self


class OnboardingApproveResponse(BaseModel):
    application_id: UUID
    merchant_id: UUID
    tenant_id: UUID
    display_name: str
    plan_label: str
    plan_status: str
    benefits_until: date | None = None
    account_manager_user_id: UUID | None = None
    subscription_id: UUID | None = None
    subscription_no: str | None = None


class OnboardingOcrRequest(BaseModel):
    doc_type: str
    file_id: str | None = None
    tenant_id: UUID | None = None


class OnboardingOcrResponse(BaseModel):
    doc_type: str
    file_id: str | None = None
    fields: dict = Field(default_factory=dict)
    confidence: float
    stub: bool = True


class OnboardingFileUploadResponse(BaseModel):
    file_id: str
    file_name: str
    doc_type: str
    size: int


class ServiceNoteCreate(BaseModel):
    type: str = Field(default="call", description="人工跟进类型：note/call/visit/wechat/video/email/training/complaint/onboarding_assist/other")
    content: str
    follow_up_at: datetime | None = None
    payload_json: dict = Field(default_factory=dict)


class RenewalRequestCreate(BaseModel):
    purchase_mode: str = Field(description="renew_same | stack | replace")
    target_plan: str
    quoted_amount_cents: int = Field(ge=0, description="与客户约定的续费金额（分），允许 0")
    catalog_price_cents: int | None = Field(default=None, ge=0, description="P10 套餐标价快照（分），选填")
    customer_confirmed: bool = False
    content: str


# ── P10 功能字典 / 套餐模板 ──────────────────────────────────────


class PlanFeatureOut(BaseModel):
    id: UUID
    code: str
    name: str
    node_type: str
    parent_id: UUID | None = None
    sort_order: int = 0
    category: str | None = None
    value_type: str | None = None
    aggregate_mode: str | None = None
    usage_period: str | None = None
    meter_key: str | None = None
    unit: str | None = None
    description: str | None = None
    is_active: bool = True
    parent_path: str | None = None
    created_by: UUID | None = None
    created_by_name: str | None = None
    created_at: datetime | None = None
    updated_by: UUID | None = None
    updated_by_name: str | None = None
    updated_at: datetime | None = None


class PlanFeatureTreeNode(PlanFeatureOut):
    children: list["PlanFeatureTreeNode"] = Field(default_factory=list)


class PlanFeatureCreate(BaseModel):
    node_type: str = Field(description="group | leaf")
    name: str = Field(min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=64, description="未传则自动 PF###")
    parent_id: UUID | None = None
    sort_order: int | None = 0
    category: str | None = None
    value_type: str | None = None
    aggregate_mode: str | None = None
    usage_period: str | None = None
    meter_key: str | None = None
    unit: str | None = None
    description: str | None = None


class PlanFeatureUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: UUID | None = None
    sort_order: int | None = None
    aggregate_mode: str | None = None
    usage_period: str | None = None
    meter_key: str | None = None
    unit: str | None = None
    description: str | None = None
    sync_to_templates: bool = False
    uniform_limit_value: int | None = None


class PlanFeatureDeactivateRequest(BaseModel):
    remove_from_templates: bool = False


class PlanTemplateOut(BaseModel):
    id: UUID
    code: str
    name: str
    plan_type: str
    sort_order: int
    is_public: bool
    is_active: bool
    stackable: bool
    replace_group: str | None = None
    billing_period: str
    price_cents: int
    quotas: dict = Field(default_factory=dict)
    features: dict = Field(default_factory=dict)
    usage_limits: dict = Field(default_factory=dict)
    allowed_entity_types: list[str] = Field(default_factory=list)
    description: str | None = None
    code_source: str | None = None
    active_subscription_count: int = 0
    created_by: UUID | None = None
    created_by_name: str | None = None
    created_at: datetime | None = None
    updated_by: UUID | None = None
    updated_by_name: str | None = None
    updated_at: datetime | None = None


class PlanTemplateListResponse(BaseModel):
    items: list[PlanTemplateOut]
    total: int
    page: int
    page_size: int


class PlanTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    plan_type: str = Field(description="main | addon")
    code: str | None = Field(default=None, max_length=64, description="未传则自动 PL###")
    sort_order: int | None = None
    stackable: bool | None = None
    replace_group: str | None = None
    billing_period: str = "yearly"
    price_cents: int = Field(default=0, ge=0)
    allowed_entity_types: list[str] = Field(default_factory=list)
    quotas: dict | None = None
    features: dict | None = None
    usage_limits: dict | None = None
    feature_values: dict | None = Field(
        default=None, description="可选：按字典 code→值，服务端按 category 拆入三区"
    )
    description: str | None = None
    is_public: bool = False
    publish_after_save: bool = False


class PlanTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None
    stackable: bool | None = None
    replace_group: str | None = None
    billing_period: str | None = None
    price_cents: int | None = Field(default=None, ge=0)
    allowed_entity_types: list[str] | None = None
    quotas: dict | None = None
    features: dict | None = None
    usage_limits: dict | None = None
    feature_values: dict | None = None
    description: str | None = None
    is_public: bool | None = None
    publish_after_save: bool = False


# ── P02 状态机 ──────────────────────────────────────────────────


class MerchantSuspendRequest(BaseModel):
    reason_code: str
    reason_text: str


class MerchantResumeRequest(BaseModel):
    note: str | None = None


class MerchantCloseRequest(BaseModel):
    reason_code: str
    reason_text: str
    ack_irreversible: bool = False


class MerchantAssignRequest(BaseModel):
    account_manager_user_id: UUID | None = None
    remark: str | None = None
    clear: bool = False


class MerchantBatchAssignRequest(BaseModel):
    tenant_ids: list[UUID]
    account_manager_user_id: UUID
    remark: str | None = None


class MerchantBatchAssignResponse(BaseModel):
    assigned: int
    tenant_ids: list[UUID]


class ShopCsUserItem(BaseModel):
    id: UUID
    display_name: str
    phone: str | None = None
    is_active: bool = True


class ShopCsUserListResponse(BaseModel):
    items: list[ShopCsUserItem]


class ShopMerchantTagListResponse(BaseModel):
    items: list[ShopMerchantTagItem]


class MerchantTagsPutRequest(BaseModel):
    tag_ids: list[UUID] = Field(default_factory=list)
    create_names: list[str] = Field(default_factory=list)


class MerchantTagsPutResponse(BaseModel):
    tags: list[str] = Field(default_factory=list)
    tag_items: list[ShopMerchantTagItem] = Field(default_factory=list)


# ── P11 订阅 ────────────────────────────────────────────────────


class SubscriptionCreateRequest(BaseModel):
    tenant_id: UUID
    plan_code: str
    plan_label: str | None = None
    purchase_mode: str = Field(description="stack | replace")
    effective_at: date | None = None
    expires_at: date | None = None
    catalog_price_cents: int | None = Field(default=None, ge=0)
    paid_amount_cents: int = Field(ge=0)
    source: str = "manual"
    remark: str | None = None
    renewal_request_id: UUID | None = None


class SubscriptionReplaceRequest(BaseModel):
    target_plan_code: str
    effective_at: date | None = None
    expires_at: date | None = None
    catalog_price_cents: int | None = Field(default=None, ge=0)
    paid_amount_cents: int = Field(ge=0)
    remark: str | None = None


class SubscriptionRenewRequest(BaseModel):
    effective_at: date | None = None
    expires_at: date | None = None
    catalog_price_cents: int | None = Field(default=None, ge=0)
    paid_amount_cents: int = Field(ge=0)
    remark: str | None = None
    renewal_request_id: UUID | None = None


class SubscriptionCancelRequest(BaseModel):
    remark: str | None = None


class SubscriptionOut(BaseModel):
    id: UUID
    subscription_no: str
    tenant_id: UUID
    merchant_display_name: str | None = None
    plan_id: UUID
    plan_code: str | None = None
    plan_name: str | None = None
    plan_type: str | None = None
    status: str
    purchase_mode: str
    source: str
    effective_at: date
    expires_at_inclusive: date
    paid_at: datetime | None = None
    catalog_price_cents: int
    paid_amount_cents: int
    previous_subscription_id: UUID | None = None
    plan_snapshot: dict = Field(default_factory=dict)
    operator_id: UUID | None = None
    operator_name: str | None = None
    remark: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    status_label: str | None = None
    display_status: str | None = None
    plan_type_label: str | None = None
    has_pending_renewal: bool = False
    billing_period: str | None = None


class SubscriptionListResponse(BaseModel):
    items: list[SubscriptionOut]
    total: int
    page: int
    page_size: int


# ── M4 商品 / 审核 ──────────────────────────────────────────────


class ProductCreateRequest(BaseModel):
    shop_id: UUID | None = None
    type: str
    name: str
    subtitle: str | None = None
    cover_url: str | None = None
    price_cents: int = Field(default=0, ge=0)
    line_price_cents: int | None = Field(default=None, ge=0)
    category_id: UUID | None = None
    ref_type: str | None = None
    ref_id: UUID | None = None
    # None = 继承店铺 A19 退款默认（#a19）
    refund_policy: str | None = None
    service_times: int | None = Field(default=None, ge=1, le=9999)
    extra: dict | None = None


class ProductPatchRequest(BaseModel):
    name: str | None = None
    subtitle: str | None = None
    cover_url: str | None = None
    price_cents: int | None = Field(default=None, ge=0)
    line_price_cents: int | None = Field(default=None, ge=0)
    category_id: UUID | None = None
    refund_policy: str | None = None
    ref_type: str | None = None
    ref_id: UUID | None = None
    extra: dict | None = None


class ProductOut(BaseModel):
    id: UUID
    tenant_id: UUID
    shop_id: UUID
    type: str
    name: str
    subtitle: str | None = None
    cover_url: str | None = None
    price_cents: int
    line_price_cents: int | None = None
    status: str
    category_id: UUID | None = None
    category_name: str | None = None
    category_path_label: str | None = None
    ref_type: str | None = None
    ref_id: UUID | None = None
    last_review_id: UUID | None = None
    compliance_flags: list = Field(default_factory=list)
    refund_policy: str
    sales_count: int = 0
    extra: dict = Field(default_factory=dict)
    # A02 公域列：mapped|none|rejected；不适用时 null（展示 —）
    channel_mount: str | None = None
    channel_mount_label: str = "—"
    created_by_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PlatformCategoryOut(BaseModel):
    id: UUID
    parent_id: UUID | None = None
    name: str
    code: str
    code_source: str = "auto"
    platform_fee_bps: int = 0
    platform_fee_label: str = "0.0%"
    settlement_rule: str = "standard"
    require_qualifications: list[str] = Field(default_factory=list)
    require_qualifications_label: str = "—"
    status: str
    description: str | None = None
    path_label: str | None = None
    updated_by_name: str | None = None
    on_sale_ref_count: int | None = None
    pending_enable_application_id: UUID | None = None
    status_display: str | None = None
    blocked_status_label: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PlatformCategoryListResponse(BaseModel):
    items: list[PlatformCategoryOut]
    total: int
    page: int = 1
    page_size: int = 20


class PlatformCategoryCreateRequest(BaseModel):
    parent_id: UUID | None = None
    name: str
    code_source: str = "auto"
    code: str | None = None
    platform_fee_bps: int = Field(default=200, ge=0, le=3000)
    settlement_rule: str = "standard"
    require_qualifications: list[str] = Field(default_factory=list)
    description: str | None = None


class PlatformCategoryPatchRequest(BaseModel):
    name: str | None = None
    platform_fee_bps: int | None = Field(default=None, ge=0, le=3000)
    settlement_rule: str | None = None
    require_qualifications: list[str] | None = None
    description: str | None = None


class PlatformCategoryDisableRequest(BaseModel):
    reason_type: str = "政策调整"
    reason: str = Field(min_length=4, max_length=500)


class PlatformCategoryEnableRequest(BaseModel):
    """P04-D 提交启用审批。对照 #p04d。"""

    reason: str = Field(min_length=4, max_length=500)
    platform_fee_bps: int = Field(default=200, ge=0, le=3000)
    require_qualifications: list[str] = Field(default_factory=list)


class PlatformCategoryEnableRejectRequest(BaseModel):
    reject_reason: str = Field(min_length=4, max_length=500)


class CategoryEnableApplicationOut(BaseModel):
    id: UUID
    category_id: UUID
    category_name: str | None = None
    category_code: str | None = None
    category_status: str | None = None
    status_label: str | None = None
    proposed_platform_fee_bps: int = 0
    proposed_platform_fee_label: str = "0.0%"
    proposed_require_qualifications: list[str] = Field(default_factory=list)
    proposed_require_qualifications_label: str = "—"
    reason: str
    status: str
    submitted_by_name: str | None = None
    submitted_at: datetime | None = None
    reviewer_name: str | None = None
    reviewed_at: datetime | None = None
    reject_reason: str | None = None
    approver_label: str = "平台超管（Phase 1 单级审批）"


class CategoryEnableApplicationListResponse(BaseModel):
    items: list[CategoryEnableApplicationOut]
    total: int
    page: int = 1
    page_size: int = 20


class PlatformCategoryPreviewCodeRequest(BaseModel):
    parent_id: UUID | None = None
    name: str = ""


class ProductListResponse(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class ProductSubmitReviewRequest(BaseModel):
    remark: str | None = None


class ProductBatchRequest(BaseModel):
    product_ids: list[UUID] = Field(default_factory=list, max_length=50)


class ProductExportRequest(BaseModel):
    shop_id: UUID | None = None
    status: str | None = None
    type: str | None = None
    q: str | None = None
    channel_mount: str | None = None
    price_min_cents: int | None = None
    price_max_cents: int | None = None
    updated_from: datetime | None = None
    updated_to: datetime | None = None
    columns: list[str] | None = None


class ProductRejectRequest(BaseModel):
    reject_reason: str
    reject_code: str | None = None


class ProductApproveRequest(BaseModel):
    note: str | None = None


class ProductForceOffRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class ProductReviewOut(BaseModel):
    id: UUID
    product_id: UUID
    tenant_id: UUID
    product_name: str | None = None
    product_type: str | None = None
    product_status: str | None = None
    merchant_name: str | None = None
    merchant_code: str | None = None
    shop_name: str | None = None
    category_name: str | None = None
    category_path: str | None = None
    plan_label: str | None = None
    entity_type: str | None = None
    entity_status: str | None = None
    snapshot_json: dict = Field(default_factory=dict)
    auto_result: str
    auto_flags: list = Field(default_factory=list)
    manual_result: str
    reject_reason: str | None = None
    reject_code: str | None = None
    internal_note: str | None = None
    reviewer_id: UUID | None = None
    reviewer_name: str | None = None
    reviewed_at: datetime | None = None
    submitted_by: UUID | None = None
    submitted_by_name: str | None = None
    submitted_at: datetime | None = None
    paid_order_count: int = 0
    first_public_domain: bool = False
    audit_log: list = Field(default_factory=list)
    cover_preview_url: str | None = None
    ref_summary: dict | None = None


class ProductReviewListResponse(BaseModel):
    items: list[ProductReviewOut]
    total: int
    page: int
    page_size: int
    pending_count: int = 0
    flagged_count: int = 0
    reviewed_count: int = 0
    category_options: list[dict] = Field(default_factory=list)


# ── M5 订单 / 买家 / 权益 / 退款 ─────────────────────────────────


class BuyerLoginRequest(BaseModel):
    tenant_id: UUID
    code: str = Field(description="微信 code；测试可用 mock:{openid}")


class BuyerBindMobileRequest(BaseModel):
    mobile: str = Field(min_length=11, max_length=11)


class BuyerOut(BaseModel):
    id: UUID
    tenant_id: UUID
    mobile: str | None = None
    mobile_masked: str | None = None
    wx_openid: str | None = None
    nickname: str | None = None
    avatar_url: str | None = None


class BuyerLoginResponse(BaseModel):
    access_token: str
    buyer: BuyerOut


class MerchantBuyerOut(BaseModel):
    """A11 买家列表行。对照 PRD #a11。"""

    id: UUID
    tenant_id: UUID
    nickname: str | None = None
    mobile: str | None = None
    mobile_masked: str | None = None
    account_status: str = "active"  # active|blocked（Phase1 暂无封禁落库，恒 active）
    source_shop_name: str | None = None
    order_count: int = 0
    entitlement_count: int = 0
    paid_amount_cents: int = 0
    register_channel: str = "微信"
    last_order_at: datetime | None = None
    first_order_at: datetime | None = None
    created_at: datetime | None = None


class MerchantBuyerListResponse(BaseModel):
    items: list[MerchantBuyerOut]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class MerchantBuyerDetailOut(MerchantBuyerOut):
    """A11-A 详情头。"""

    pass


class BuyerLearningProgressOut(BaseModel):
    entitlement_id: UUID
    product_name: str | None = None
    shop_name: str | None = None
    entitlement_status: str | None = None
    progress_pct: int = 0
    learned_count: int = 0
    total_lessons: int = 0
    last_learned_at: datetime | None = None
    last_lesson_title: str | None = None


class BuyerLearningListResponse(BaseModel):
    items: list[BuyerLearningProgressOut]
    total: int


class OrderCreateRequest(BaseModel):
    product_id: UUID
    idempotency_key: str | None = None
    # 买家端若传 amount_cents，仅校验一致性；价格以后端 SKU 为准
    amount_cents: int | None = Field(default=None, ge=0)


_REFUND_REASON_LABELS = {
    "buyer_request": "买家申请",
    "quality": "质量问题",  # M12-A 买家
    "wrong_order": "错拍",
    "fulfill_dispute": "履约纠纷",  # A09-B 商家
    "other": "其他",
}


class OrderRefundRequest(BaseModel):
    """A09-B / M12-A：reason_code 必选（新客户端）；reason 兼容旧调用。"""

    amount_cents: int | None = Field(default=None, ge=1)
    reason_code: str | None = Field(
        default=None,
        description="buyer_request|quality|wrong_order|fulfill_dispute|other",
    )
    remark: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def _compose_reason(self):
        if self.reason_code:
            if self.reason_code not in _REFUND_REASON_LABELS:
                raise ValueError("请选择退款原因")
            text = (self.remark or "").strip()
            if self.reason_code == "other" and len(text) < 4:
                raise ValueError("其他原因至少 4 字")
            label = _REFUND_REASON_LABELS[self.reason_code]
            self.reason = f"{label}：{text}" if text else label
        elif not (self.reason or "").strip():
            raise ValueError("请选择退款原因")
        return self


class PaymentNotifyRequest(BaseModel):
    order_no: str
    transaction_id: str
    paid_amount_cents: int | None = None
    sign: str | None = None


class PaymentConfigUpsertRequest(BaseModel):
    shop_id: UUID | None = None
    wx_mch_id: str
    wx_app_id: str
    wx_api_key: str
    wx_notify_url: str | None = None
    status: str = "active"


class PaymentConfigOut(BaseModel):
    id: UUID
    tenant_id: UUID
    shop_id: UUID
    wx_mch_id: str
    wx_app_id: str
    wx_api_key_masked: str | None = None
    wx_notify_url: str | None = None
    status: str
    onboarded_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PrepayOut(BaseModel):
    mode: str
    prepay_id: str
    appId: str | None = None
    timeStamp: str | None = None
    nonceStr: str | None = None
    package: str | None = None
    signType: str | None = None
    paySign: str | None = None
    mch_id: str | None = None


class OrderTimelineItem(BaseModel):
    at: datetime | None = None
    event: str


class OrderOut(BaseModel):
    id: UUID
    tenant_id: UUID
    shop_id: UUID
    buyer_id: UUID
    product_id: UUID
    order_no: str
    type: str
    amount_cents: int
    status: str
    paid_amount_cents: int | None = None
    paid_at: datetime | None = None
    paid_channel: str | None = None
    refund_amount_cents: int | None = None
    refunded_at: datetime | None = None
    refund_reason: str | None = None
    needs_red_flush: bool = False
    invoice_status: str = "none"
    source: str = "private"
    channel: str = "微信"
    buyer_nickname: str | None = None
    buyer_mobile: str | None = None
    buyer_mobile_masked: str | None = None
    external_order_no: str | None = None
    product_name: str | None = None
    shop_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # A10 详情附加（列表可为空）
    entitlement_id: UUID | None = None
    entitlement_status: str | None = None
    entitlement_expires_at: datetime | None = None
    claim_status: str | None = None
    claim_token: str | None = None
    timeline: list[OrderTimelineItem] = Field(default_factory=list)


class CreateOrderResponse(BaseModel):
    order: OrderOut
    prepay: PrepayOut | None = None
    payment_id: UUID | None = None


class OrderListResponse(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(default_factory=dict)


_CLOSE_REASON_LABELS = {
    "buyer_abandon": "买家放弃",
    "wrong_duplicate": "错拍重复",
    "merchant_cancel": "商家取消",
    "other": "其他",
}


class OrderCloseRequest(BaseModel):
    """A09-A：close_reason_code / text；reason 为落库合成串（兼容旧客户端）。"""

    reason_code: str | None = Field(
        default=None,
        description="buyer_abandon|wrong_duplicate|merchant_cancel|other",
    )
    reason_text: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def _compose_reason(self):
        if self.reason_code:
            if self.reason_code not in _CLOSE_REASON_LABELS:
                raise ValueError("请选择关闭原因")
            text = (self.reason_text or "").strip()
            if self.reason_code == "other" and len(text) < 4:
                raise ValueError("其他原因至少 4 字")
            label = _CLOSE_REASON_LABELS[self.reason_code]
            self.reason = f"{label}：{text}" if text else label
        elif not (self.reason or "").strip():
            raise ValueError("请选择关闭原因")
        return self


class OrderResendNotifyRequest(BaseModel):
    remark: str | None = None


class EntitlementOut(BaseModel):
    id: UUID
    tenant_id: UUID
    buyer_id: UUID
    order_id: UUID
    product_id: UUID
    shop_id: UUID
    status: str
    activated_at: datetime | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None
    remaining_count: int | None = None
    total_count: int | None = None
    verify_code: str | None = None
    expires_at: datetime | None = None
    product_name: str | None = None
    product_type: str | None = None
    service_offer_id: UUID | None = None
    service_mode: str | None = None
    created_at: datetime | None = None
    # A12 列表 enrich
    buyer_nickname: str | None = None
    buyer_mobile_masked: str | None = None
    order_no: str | None = None
    shop_name: str | None = None
    has_learning_progress: bool | None = None
    learning_progress_pct: int | None = None
    learned_lesson_count: int | None = None
    total_lesson_count: int | None = None
    cover_url: str | None = None


class EntitlementListResponse(BaseModel):
    items: list[EntitlementOut]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class RefundOut(BaseModel):
    id: UUID
    order_id: UUID
    tenant_id: UUID
    amount_cents: int
    reason: str | None = None
    status: str
    initiated_by: str
    is_partial: bool = False
    needs_red_flush: bool = False
    entitlement_revoked_at: datetime | None = None
    processed_at: datetime | None = None
    created_at: datetime | None = None


class RefundListResponse(BaseModel):
    items: list[RefundOut]
    total: int
    page: int
    page_size: int


class MarkInvoiceRequest(BaseModel):
    invoice_status: str = "issued"


# ── M6 核销 / 预约 / 开票 / 学课进度 ─────────────────────────────


class VerificationLookupRequest(BaseModel):
    mobile: str | None = None
    verify_code: str | None = None


class VerificationLookupItem(BaseModel):
    entitlement_id: UUID
    buyer_id: UUID
    buyer_mobile_masked: str | None = None
    product_id: UUID
    product_name: str | None = None
    product_type: str | None = None
    shop_id: UUID
    status: str
    remaining_count: int | None = None
    total_count: int | None = None
    verify_code: str | None = None
    booking_id: UUID | None = None
    booking_slot: str | None = None
    last_verified_at: datetime | None = None
    last_operator_name: str | None = None


class VerificationLookupResponse(BaseModel):
    """result: can_redeem | invalid | already_used | refunded | exhausted | multi"""

    result: str = "invalid"
    message: str | None = None
    item: VerificationLookupItem | None = None
    items: list[VerificationLookupItem] = Field(default_factory=list)


class VerificationExecuteRequest(BaseModel):
    entitlement_id: UUID
    booking_id: UUID | None = None
    deducted_count: int = Field(default=1, ge=1, le=100)
    idempotency_key: str | None = Field(default=None, max_length=64)
    shop_id: UUID | None = None


class VerificationOut(BaseModel):
    id: UUID
    tenant_id: UUID
    shop_id: UUID
    buyer_id: UUID
    entitlement_id: UUID
    booking_id: UUID | None = None
    type: str
    status: str
    operator_id: UUID | None = None
    operator_name: str | None = None
    verify_code: str | None = None
    idempotency_key: str | None = None
    deducted_count: int
    remaining_count: int | None = None
    remaining_before: int | None = None
    remaining_after: int | None = None
    verification_no: str | None = None
    entitlement_status: str | None = None
    buyer_mobile_masked: str | None = None
    product_name: str | None = None
    booking_slot: str | None = None
    created_at: datetime | None = None


class VerificationListResponse(BaseModel):
    items: list[VerificationOut]
    total: int
    page: int
    page_size: int


class BookingCreateRequest(BaseModel):
    entitlement_id: UUID
    slot_id: UUID | None = None
    booked_date: date | None = None
    booked_time_slot: str | None = Field(default=None, max_length=32)


class BookingCancelRequest(BaseModel):
    reason: str | None = None


class BookingOut(BaseModel):
    id: UUID
    tenant_id: UUID
    shop_id: UUID
    buyer_id: UUID
    entitlement_id: UUID
    service_product_id: UUID
    slot_id: UUID | None = None
    status: str
    booked_date: date
    booked_time_slot: str
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    product_name: str | None = None
    buyer_mobile_masked: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    booking_no: str | None = None
    status_label: str | None = None
    shop_name: str | None = None
    verify_code: str | None = None
    order_id: UUID | None = None
    order_no: str | None = None
    offer_id: UUID | None = None


class ServiceOfferCreateRequest(BaseModel):
    shop_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    mode: str = Field(pattern="^(booking|times_card)$")
    total_times: int | None = Field(default=None, ge=1, le=999999)
    valid_days: int | None = Field(default=None, ge=1, le=3650)
    duration_minutes: int = Field(default=60, ge=15, le=24 * 60)


class ServiceOfferPatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    mode: str | None = Field(default=None, pattern="^(booking|times_card)$")
    total_times: int | None = Field(default=None, ge=1, le=999999)
    valid_days: int | None = Field(default=None, ge=1, le=3650)
    duration_minutes: int | None = Field(default=None, ge=15, le=24 * 60)


class ServiceOfferOut(BaseModel):
    id: UUID
    tenant_id: UUID
    shop_id: UUID
    title: str
    mode: str
    status: str
    total_times: int | None = None
    valid_days: int | None = None
    duration_minutes: int = 60
    ref_product_count: int = 0
    open_slot_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ServiceOfferListResponse(BaseModel):
    items: list[ServiceOfferOut]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class ServiceOfferExportRequest(BaseModel):
    shop_id: UUID | None = None
    status: str | None = None
    mode: str | None = None
    q: str | None = None
    columns: list[str] | None = None


class ServiceSlotOut(BaseModel):
    id: UUID
    service_offer_id: UUID
    start_at: datetime
    end_at: datetime
    capacity: int
    booked_count: int
    status: str
    selectable: bool = False


class ServiceSlotListResponse(BaseModel):
    items: list[ServiceSlotOut]
    total: int


class ServiceSlotDailyWindow(BaseModel):
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")


class ServiceSlotBatchRequest(BaseModel):
    date_from: date
    date_to: date
    daily_windows: list[ServiceSlotDailyWindow] = Field(min_length=1)
    capacity: int = Field(default=1, ge=1, le=9999)
    skip_weekends: bool = False
    skip_overlap: bool = True


class ServiceSlotBatchPreviewOut(BaseModel):
    will_create: int
    skipped_weekend: int = 0
    skipped_overlap: int = 0
    preview: list[ServiceSlotOut] = Field(default_factory=list)


class MpServiceSlotsResponse(BaseModel):
    mode: str
    slots: list[ServiceSlotOut] = Field(default_factory=list)
    remaining_times: int | None = None
    valid_until: date | None = None
    total_times: int | None = None
    duration_minutes: int | None = None


class BookingListResponse(BaseModel):
    items: list[BookingOut]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class BookingExportRequest(BaseModel):
    booked_date: date | None = None
    booked_from: date | None = None
    booked_to: date | None = None
    buyer_id: UUID | None = None
    shop_id: UUID | None = None
    status: str | None = None
    q: str | None = None
    columns: list[str] | None = None


# ── A04–A06 专栏 / 课时 / 资料包 ──────────────────────────────────


class ColumnCreateRequest(BaseModel):
    shop_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    intro: str | None = None


class ColumnPatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    intro: str | None = None


class ColumnOut(BaseModel):
    id: UUID
    tenant_id: UUID
    shop_id: UUID
    title: str
    intro: str | None = None
    status: str
    lesson_count: int = 0
    published_lesson_count: int = 0
    ref_product_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ColumnListResponse(BaseModel):
    items: list[ColumnOut]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class ColumnExportRequest(BaseModel):
    shop_id: UUID | None = None
    status: str | None = None
    q: str | None = None
    ref_min: int | None = None
    ref_max: int | None = None
    updated_from: date | None = None
    updated_to: date | None = None
    columns: list[str] | None = None


class LessonCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    media_type: str = Field(default="video", pattern="^(video|audio|article)$")
    media_id: str | None = Field(default=None, max_length=64)
    media_url: str | None = Field(default=None, max_length=500)
    content_body: str | None = Field(default=None, max_length=50000)
    duration_sec: int = Field(default=0, ge=0, le=86400)
    is_trial: bool = False
    trial_seconds: int | None = Field(default=None, ge=1, le=3600)
    sort_order: int | None = Field(default=None, ge=0)


class LessonPatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    media_type: str | None = Field(default=None, pattern="^(video|audio|article)$")
    media_id: str | None = Field(default=None, max_length=64)
    media_url: str | None = Field(default=None, max_length=500)
    content_body: str | None = Field(default=None, max_length=50000)
    duration_sec: int | None = Field(default=None, ge=0, le=86400)
    is_trial: bool | None = None
    trial_seconds: int | None = Field(default=None, ge=1, le=3600)
    sort_order: int | None = Field(default=None, ge=0)


class LessonOut(BaseModel):
    id: UUID
    column_id: UUID
    title: str
    media_type: str
    media_id: str | None = None
    media_url: str | None = None
    content_body: str | None = None
    duration_sec: int = 0
    is_trial: bool = False
    trial_seconds: int | None = None
    sort_order: int = 0
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LessonListResponse(BaseModel):
    items: list[LessonOut]
    total: int


class DigitalPackageCreateRequest(BaseModel):
    shop_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    deliver_mode: str = Field(default="download", pattern="^(download|online_view)$")
    max_downloads: int | None = Field(default=None, ge=1, le=9999)


class DigitalPackagePatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    deliver_mode: str | None = Field(default=None, pattern="^(download|online_view)$")
    max_downloads: int | None = Field(default=None, ge=1, le=9999)


class DigitalAssetOut(BaseModel):
    id: UUID
    package_id: UUID
    file_id: str
    file_name: str
    file_url: str
    mime: str
    size_bytes: int
    previewable: bool
    sort_order: int
    created_at: datetime | None = None


class DigitalPackageOut(BaseModel):
    id: UUID
    tenant_id: UUID
    shop_id: UUID
    title: str
    deliver_mode: str
    max_downloads: int | None = None
    status: str
    file_count: int = 0
    previewable_count: int = 0
    ref_product_count: int = 0
    assets: list[DigitalAssetOut] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DigitalPackageListResponse(BaseModel):
    items: list[DigitalPackageOut]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class DigitalPackageExportRequest(BaseModel):
    shop_id: UUID | None = None
    status: str | None = None
    q: str | None = None
    columns: list[str] | None = None


class DigitalAssetCreateRequest(BaseModel):
    file_id: str = Field(min_length=1, max_length=64)
    file_name: str = Field(min_length=1, max_length=255)
    file_url: str | None = Field(default=None, max_length=500)
    mime: str | None = Field(default=None, max_length=100)
    size_bytes: int = Field(default=0, ge=0)


class ContentFileUploadOut(BaseModel):
    file_id: str
    file_name: str
    file_url: str
    mime: str
    size_bytes: int
    previewable: bool


class InvoiceCreateRequest(BaseModel):
    order_id: UUID
    invoice_type: str = "normal"
    title_type: str  # person|company
    title: str = Field(min_length=1, max_length=200)
    tax_no: str | None = Field(default=None, max_length=32)
    bank_name: str | None = None
    bank_account: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None


class InvoiceIssueRequest(BaseModel):
    invoice_no: str = Field(min_length=1, max_length=64)
    invoice_url: str | None = Field(default=None, max_length=500)
    remark: str | None = Field(default=None, max_length=200)


class InvoiceRejectRequest(BaseModel):
    reason: str = Field(min_length=4, max_length=500)


class InvoiceOut(BaseModel):
    id: UUID
    tenant_id: UUID
    shop_id: UUID
    buyer_id: UUID
    order_id: UUID
    order_no: str | None = None
    invoice_type: str
    title_type: str
    title: str
    tax_no: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    amount_cents: int
    status: str
    issued_at: datetime | None = None
    invoice_no: str | None = None
    application_no: str | None = None
    invoice_url: str | None = None
    remark: str | None = None
    needs_red_flush: bool = False
    reject_reason: str | None = None
    operator_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InvoiceListResponse(BaseModel):
    items: list[InvoiceOut]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class InvoiceExportRequest(BaseModel):
    status: str | None = None
    q: str | None = None
    shop_id: UUID | None = None
    title_type: str | None = None
    created_from: date | None = None
    created_to: date | None = None


class ShopExportTaskOut(BaseModel):
    id: UUID
    resource: str
    status: str
    file_name: str | None = None
    row_count: int = 0
    error: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


InvoiceExportTaskOut = ShopExportTaskOut


class OrderExportRequest(BaseModel):
    status: str | None = None
    q: str | None = None
    source: str | None = None
    shop_id: UUID | None = None
    product_type: str | None = None
    amount_min: int | None = None
    amount_max: int | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    external_order_no: str | None = None
    columns: list[str] | None = None


class BuyerExportRequest(BaseModel):
    q: str | None = None
    tab: str | None = None
    shop_id: UUID | None = None
    account_status: str | None = None
    order_count_min: int | None = None
    entitlement_count_min: int | None = None
    registered_from: date | None = None
    registered_to: date | None = None
    last_order_from: date | None = None
    last_order_to: date | None = None
    buyer_ids: list[UUID] | None = None


class EntitlementExportRequest(BaseModel):
    status: str | None = None
    q: str | None = None
    product_type: str | None = None
    shop_id: UUID | None = None
    activated_from: date | None = None
    activated_to: date | None = None
    expires_from: date | None = None
    expires_to: date | None = None


class VerificationExportRequest(BaseModel):
    q: str | None = None
    shop_id: UUID | None = None
    created_from: str | None = None
    created_to: str | None = None
    operator_id: UUID | None = None


class MerchantExportRequest(BaseModel):
    q: str | None = None
    onboarding_status: str | None = None
    plan_status: str | None = None
    entity_type: str | None = None
    plan_label: str | None = None
    fee_tier: str | None = None
    account_manager_user_id: UUID | None = None
    tag_ids: str | None = None
    benefits_from: date | None = None
    benefits_until: date | None = None
    store_count_min: int | None = None
    store_count_max: int | None = None
    created_from: date | None = None
    created_until: date | None = None
    tab: str | None = None
    include_not_onboarded: bool = True
    sort_by: str | None = "created_at"
    sort_dir: str | None = "desc"
    columns: list[str] | None = None


class SettlementExportRequest(BaseModel):
    q: str | None = None
    status: str | None = None
    view: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    sort_by: str | None = None
    sort_dir: str | None = "desc"
    columns: list[str] | None = None


class SmsLogExportRequest(BaseModel):
    purpose: str | None = None
    status: str | None = None
    q: str | None = None
    range_key: str | None = "30d"
    date_from: str | None = None
    date_until: str | None = None


class SmsSignatureExportRequest(BaseModel):
    q: str | None = None
    status: str | None = None
    columns: list[str] | None = None


class SmsTemplateExportRequest(BaseModel):
    purpose: str | None = None
    status: str | None = None
    columns: list[str] | None = None


class SmsAssignmentExportRequest(BaseModel):
    q: str | None = None
    assign_status: str | None = None
    columns: list[str] | None = None


class ModerationExportRequest(BaseModel):
    q: str | None = None
    status: str | None = None
    case_type: str | None = None
    source: str | None = None
    view: str | None = None
    columns: list[str] | None = None


class SubscriptionExportRequest(BaseModel):
    tenant_id: UUID | None = None
    status: str | None = None
    plan_code: str | None = None
    q: str | None = None
    view: str | None = None
    sort_by: str | None = None
    sort_dir: str | None = "desc"
    columns: list[str] | None = None


class PaymentOnboardingExportRequest(BaseModel):
    status: str | None = None
    q: str | None = None
    entity_type: str | None = None
    account_manager_user_id: str | None = None
    sort_by: str | None = None
    sort_dir: str | None = "desc"
    columns: list[str] | None = None


class LessonProgressUpsertRequest(BaseModel):
    course_id: UUID
    position_sec: int = Field(default=0, ge=0)
    progress_pct: int = Field(default=0, ge=0, le=100)


class LessonProgressOut(BaseModel):
    id: UUID
    tenant_id: UUID
    buyer_id: UUID
    entitlement_id: UUID
    course_id: UUID
    lesson_id: UUID
    position_sec: int
    progress_pct: int
    last_learned_at: datetime | None = None
    updated_at: datetime | None = None


class LessonItemOut(BaseModel):
    id: UUID
    title: str
    duration_sec: int = 0
    is_trial: bool = False
    trial_seconds: int | None = None
    sort: int = 0
    status: str = "todo"  # todo|learning|done
    progress_pct: int = 0
    position_sec: int = 0
    locked: bool = False
    media_url: str | None = None
    media_type: str | None = None


class CourseOutlineOut(BaseModel):
    entitlement_id: UUID
    product_id: UUID
    course_id: UUID
    product_name: str | None = None
    entitlement_status: str
    progress_pct: int = 0
    learned_count: int = 0
    total_count: int = 0
    lessons: list[LessonItemOut] = Field(default_factory=list)


class MaterialFileOut(BaseModel):
    id: str
    name: str
    size_bytes: int = 0
    mime: str = "application/octet-stream"
    can_preview: bool = False
    download_count: int = 0
    remaining_downloads: int | None = None
    download_disabled: bool = False


class MaterialsOut(BaseModel):
    entitlement_id: UUID
    product_id: UUID
    product_name: str | None = None
    entitlement_status: str
    deliver_mode: str = "online_view"
    max_downloads: int | None = None
    total_download_count: int = 0
    files: list[MaterialFileOut] = Field(default_factory=list)


class MaterialDownloadOut(BaseModel):
    file_id: str
    download_url: str
    download_count: int
    remaining_downloads: int | None = None
    deliver_mode: str = "online_view"


# ── M7 公域映射 / 领权 ───────────────────────────────────────────


class ChannelSettingOut(BaseModel):
    tenant_id: UUID
    enabled_combos: list[str] = Field(default_factory=list)
    deal_link: str = "1"
    path_mode: str = "A"
    bind_scope: str = "tenant"
    bind_status: str = "unbound"
    bind_status_label: str = "未绑定"
    last_synced_at: datetime | None = None
    webhook_verified: bool = False
    webhook_tested_at: datetime | None = None
    douyin_shop_id: str | None = None
    douyin_configured: bool = False
    webhook_url: str | None = None
    has_webhook_secret: bool = False
    link2_available: bool = False
    path_b_available: bool = False
    config_state: str = "draft"
    config_state_label: str = "未配置"
    combo_label: str = "链路① · 路径A"
    demo_tools_enabled: bool = False


class ChannelDemoOrderRequest(BaseModel):
    buyer_mobile: str | None = Field(default=None, pattern=r"^1\d{10}$")


class ChannelDemoOrderOut(BaseModel):
    status: str
    order_id: str | None = None
    order_status: str | None = None
    claim_token: str | None = None
    claim_url: str | None = None
    orders_path: str = "/shop/orders"
    buyer_mobile: str | None = None
    external_order_no: str | None = None
    product_name: str | None = None
    message: str | None = None


class ChannelSettingSaveRequest(BaseModel):
    enabled_combos: list[str] | None = None
    douyin_shop_id: str | None = None
    douyin_webhook_secret: str | None = None
    deal_link: str | None = None
    path_mode: str | None = None
    bind_scope: str | None = None


class ChannelBindRequest(BaseModel):
    douyin_shop_id: str = Field(..., min_length=1, max_length=64)
    douyin_webhook_secret: str | None = None
    bind_scope: str | None = None


class ChannelMappingCreateRequest(BaseModel):
    product_id: UUID
    channel: str = "douyin"
    channel_product_id: str = Field(min_length=1, max_length=64)
    channel_product_url: str | None = None
    combo: str = "1A"
    # A14-A 向导扩展
    external_title: str | None = Field(default=None, min_length=2, max_length=60)
    external_category: str | None = Field(default=None, max_length=120)
    sync_mode: str = Field(default="create_new", description="create_new（Phase1）")
    submit_mode: str = Field(
        default="mapped",
        description="mapped=直接挂载（兼容旧调用）；audit=pending+submitted（A14-A）",
    )


class ChannelPreviewSyncRequest(BaseModel):
    """A14-A 步2：预同步分配外部商品 ID。"""

    product_id: UUID
    combo: str = "1A"
    external_title: str = Field(min_length=2, max_length=60)
    external_category: str = Field(min_length=1, max_length=120)
    sync_mode: str = "create_new"


class ChannelPreviewSyncOut(BaseModel):
    channel_product_id: str
    external_title: str
    external_category: str
    price_cents: int
    product_name: str | None = None
    cover_url: str | None = None
    path_label: str = "A"
    douyin_shop_id: str | None = None
    sync_mode: str = "create_new"


class ChannelMappingOut(BaseModel):
    id: UUID
    tenant_id: UUID
    shop_id: UUID
    product_id: UUID
    product_name: str | None = None
    product_review_status: str | None = None
    channel: str
    channel_label: str | None = None
    channel_product_id: str
    channel_product_url: str | None = None
    path_label: str | None = None
    status: str
    status_label: str | None = None
    external_audit_status: str | None = None
    external_audit_label: str | None = None
    mount_blocked_code: str | None = None
    mount_blocked_reason: str | None = None
    blocked_at: datetime | None = None
    synced_at: datetime | None = None
    created_at: datetime | None = None


class ChannelMappingListResponse(BaseModel):
    items: list[ChannelMappingOut]
    total: int
    page: int
    page_size: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class ChannelMappingExportRequest(BaseModel):
    status: str | None = None
    q: str | None = None
    shop_id: UUID | None = None
    external_audit_status: str | None = None
    path: str | None = None
    mapped_from: str | None = None
    mapped_to: str | None = None
    columns: list[str] | None = None


class StoreExportRequest(BaseModel):
    q: str | None = None
    tab: str | None = None
    status: str | None = None
    product_count_min: int | None = None
    product_count_max: int | None = None
    created_from: str | None = None
    created_to: str | None = None
    sort: str | None = None
    include_closed: bool = False
    columns: list[str] | None = None


class ChannelExternalAuditRequest(BaseModel):
    """Mock/联调：模拟抖店外部审核回调。"""

    result: str = Field(description="approved|rejected")
    reject_code: str | None = Field(default=None, max_length=64)
    reject_reason: str | None = Field(default=None, max_length=500)


class ChannelResubmitRequest(BaseModel):
    """A14-B：修改并重新提交。"""

    note: str | None = Field(default=None, max_length=200)


class ChannelAuditLogOut(BaseModel):
    id: UUID
    tenant_id: UUID
    shop_id: UUID | None = None
    product_id: UUID | None = None
    channel: str
    event: str
    detail_json: dict = Field(default_factory=dict)
    created_at: datetime | None = None


class ChannelAuditListResponse(BaseModel):
    items: list[ChannelAuditLogOut]
    total: int


class DouyinOrderWebhookRequest(BaseModel):
    event_id: str
    event_type: str = "order.paid"
    tenant_id: UUID | None = None
    douyin_shop_id: str | None = None
    channel_product_id: str
    external_order_no: str
    buyer_mobile: str
    paid_amount_cents: int
    sign: str | None = None
    combo: str = "1A"


class DouyinRefundWebhookRequest(BaseModel):
    event_id: str
    event_type: str = "order.refund"
    external_order_no: str
    reason: str | None = None
    sign: str | None = None
    tenant_id: UUID | None = None
    douyin_shop_id: str | None = None


class ClaimInfoOut(BaseModel):
    token: str
    status: str
    tenant_id: UUID | None = None
    shop_id: UUID | None = None
    product_name: str | None = None
    mobile_tail: str | None = None
    mobile_masked: str | None = None
    order_id: UUID | None = None
    expires_at: datetime | None = None
    order_status: str | None = None
    message: str | None = None


class ClaimConfirmResponse(BaseModel):
    status: str
    order_id: UUID
    entitlement_id: UUID | None = None
    order_status: str


class AnalyticsStoreOption(BaseModel):
    id: UUID
    name: str
    status: str


class AnalyticsResumeBanner(BaseModel):
    show: bool
    paused_store_count: int = 0
    pending_order_count: int = 0


class AnalyticsSummaryOut(BaseModel):
    """A01 交易看板指标。对照 #a01。"""

    range: str
    date_from: str
    date_to: str
    shop_id: UUID | None = None
    gmv_cents: int = 0
    order_count: int = 0
    payment_conversion: float | None = None
    pending_refunds: int = 0
    pending_verify: int = 0
    pending_invoices: int = 0
    pending_claims: int = 0
    off_sale_products: int = 0
    resume: AnalyticsResumeBanner
    stores: list[AnalyticsStoreOption] = Field(default_factory=list)


class AnalyticsTrendPoint(BaseModel):
    date: str
    gmv_cents: int = 0
    order_count: int = 0


class AnalyticsShareItem(BaseModel):
    key: str
    label: str
    amount_cents: int = 0
    count: int = 0
    percent: float = 0.0


class AnalyticsTrendsOut(BaseModel):
    range: str
    date_from: str
    date_to: str
    daily: list[AnalyticsTrendPoint] = Field(default_factory=list)
    by_category: list[AnalyticsShareItem] = Field(default_factory=list)
    by_channel: list[AnalyticsShareItem] = Field(default_factory=list)


class ShopPermissionAuditOut(BaseModel):
    id: UUID
    target_user_id: UUID
    operator_user_id: UUID
    operator_name: str
    action: str
    action_label: str
    summary: str
    created_at: datetime


class ShopPermissionAuditListResponse(BaseModel):
    items: list[ShopPermissionAuditOut]
    total: int
    page: int
    page_size: int


# ── 买家店首页 / 商品详情（M02 / M03）────────────────────────────


class MpStoreBriefOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    logo_url: str | None = None
    status: str
    merchant_status: str
    intro: str | None = None
    service_phone: str | None = None


class MpStoreResolveOut(BaseModel):
    shop_id: UUID
    tenant_id: UUID
    name: str
    status: str


class MpStoreProductCard(BaseModel):
    id: UUID
    type: str
    name: str
    subtitle: str | None = None
    cover_url: str | None = None
    price_cents: int
    line_price_cents: int | None = None
    status: str
    sales_count: int = 0


class MpStorefrontResponse(BaseModel):
    shop: MpStoreBriefOut
    products: list[MpStoreProductCard]
    total: int
    page: int
    page_size: int
    has_more: bool


class MpProductLessonPreview(BaseModel):
    id: UUID
    title: str
    duration_sec: int = 0
    is_trial: bool = False
    trial_seconds: int | None = None
    sort: int = 0
    locked: bool = True


class MpProductDetailOut(BaseModel):
    id: UUID
    shop_id: UUID
    tenant_id: UUID
    type: str
    name: str
    subtitle: str | None = None
    cover_url: str | None = None
    price_cents: int
    line_price_cents: int | None = None
    status: str
    sales_count: int = 0
    purchase_state: str = "not_purchased"  # not_purchased|purchased|trial_available
    entitlement_id: UUID | None = None
    lesson_count: int | None = None
    asset_count: int | None = None
    service_mode: str | None = None
    service_times: int | None = None
    lessons: list[MpProductLessonPreview] = Field(default_factory=list)
    shop_name: str | None = None
    shop_status: str | None = None
    merchant_status: str | None = None
