"""CRM-2/3 v0.7 Pydantic Schemas（商机/管道/产品/报价/合同/订单/收款）。

Phase B 仅实现 deal + pipeline；其它实体 schema 在后续 Phase 中按需扩展。
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.crm import (
    CONTRACT_AMENDMENT_CHANGE_TYPES,
    CONTRACT_AMENDMENT_STATUSES,
    CONTRACT_STATUSES,
    CONTRACT_TYPES,
    DEAL_SOURCES,
    DEAL_STATUSES,
    DELIVERY_NOTE_STATUSES,
    INVOICE_STATUSES,
    INVOICE_TYPES,
    ORDER_SOURCES,
    ORDER_STATUSES,
    PAYMENT_METHODS,
    PAYMENT_STATUSES,
    QUOTE_STATUSES,
    REFUND_STATUSES,
)


# ============================================================
# 销售管道 + 阶段
# ============================================================


class PipelineStageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    probability: int = Field(default=0, ge=0, le=100)
    is_won_stage: bool = False
    is_lost_stage: bool = False
    is_closed_stage: bool = False
    color: str | None = Field(default=None, max_length=16)
    max_stay_days: int | None = Field(default=None, ge=1)
    is_active: bool = True


class PipelineStageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    is_won_stage: bool | None = None
    is_lost_stage: bool | None = None
    is_closed_stage: bool | None = None
    color: str | None = None
    max_stay_days: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class PipelineStageOut(BaseModel):
    id: UUID
    pipeline_id: UUID
    name: str
    sort_order: int
    probability: int
    is_won_stage: bool
    is_lost_stage: bool
    is_closed_stage: bool
    color: str | None
    max_stay_days: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PipelineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_default: bool = False
    is_active: bool = True
    stages: list[PipelineStageCreate] = Field(default_factory=list)


class PipelineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_default: bool | None = None
    is_active: bool | None = None


class PipelineOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    stages: list[PipelineStageOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ============================================================
# 商机
# ============================================================


def validate_deal_status(value: str) -> None:
    if value not in DEAL_STATUSES:
        raise ValueError(f"status 必须是 {DEAL_STATUSES} 之一")


def validate_deal_source(value: str | None) -> None:
    if value is not None and value not in DEAL_SOURCES:
        raise ValueError(f"source 必须是 {DEAL_SOURCES} 之一")


class DealLineItemCreate(BaseModel):
    product_id: UUID | None = None
    product_name: str = Field(default="", max_length=200)
    description: str | None = Field(default=None, max_length=500)
    unit: str | None = Field(default=None, max_length=30)
    quantity: float = Field(default=1, ge=0)
    unit_price: float = Field(default=0, ge=0)
    discount_percent: float = Field(default=0, ge=0, le=100)
    subtotal: float | None = Field(default=None, ge=0)
    sort_order: int | None = None


class DealLineItemOut(BaseModel):
    id: UUID
    product_id: UUID | None
    product_name: str
    description: str | None
    unit: str | None
    quantity: float
    unit_price: float
    discount_percent: float
    subtotal: float
    sort_order: int

    model_config = {"from_attributes": True}


class DealTeamMemberAdd(BaseModel):
    user_id: UUID
    role: str = Field(default="member", max_length=30)


class DealTeamMemberOut(BaseModel):
    id: UUID
    deal_id: UUID
    user_id: UUID
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class DealCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    customer_id: UUID
    contact_id: UUID | None = None
    pipeline_id: UUID | None = None  # 缺省取租户默认管道
    stage_id: UUID | None = None  # 缺省取管道第一阶段
    amount: float = Field(default=0, ge=0)
    expected_close_date: datetime | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    status: str = "open"
    source: str | None = None
    description: str | None = None
    next_step: str | None = Field(default=None, max_length=200)
    deal_type: str | None = Field(default=None, max_length=20)
    priority: str | None = Field(default=None, max_length=10)
    competitor: str | None = Field(default=None, max_length=200)
    contact_role: str | None = Field(default=None, max_length=50)
    campaign_id: UUID | None = None
    owner_user_id: UUID | None = None
    territory_id: UUID | None = None
    lines: list[DealLineItemCreate] = Field(default_factory=list)
    extra_data: dict = Field(default_factory=dict)

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        validate_deal_status(v)
        return v

    @field_validator("source")
    @classmethod
    def _valid_source(cls, v: str | None) -> str | None:
        validate_deal_source(v)
        return v


class DealUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    customer_id: UUID | None = None
    contact_id: UUID | None = None
    pipeline_id: UUID | None = None
    stage_id: UUID | None = None
    amount: float | None = Field(default=None, ge=0)
    expected_close_date: datetime | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    status: str | None = None
    source: str | None = None
    description: str | None = None
    next_step: str | None = Field(default=None, max_length=200)
    deal_type: str | None = Field(default=None, max_length=20)
    priority: str | None = Field(default=None, max_length=10)
    competitor: str | None = Field(default=None, max_length=200)
    contact_role: str | None = Field(default=None, max_length=50)
    campaign_id: UUID | None = None
    owner_user_id: UUID | None = None
    territory_id: UUID | None = None
    lines: list[DealLineItemCreate] | None = None
    extra_data: dict | None = None

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str | None) -> str | None:
        if v is not None:
            validate_deal_status(v)
        return v

    @field_validator("source")
    @classmethod
    def _valid_source(cls, v: str | None) -> str | None:
        if v is not None:
            validate_deal_source(v)
        return v


class DealStageChange(BaseModel):
    stage_id: UUID
    note: str | None = None


class DealClose(BaseModel):
    status: str  # won | lost | abandoned
    amount: float | None = Field(default=None, ge=0)  # won 时必填
    loss_reason: str | None = None  # lost 时必填（兼容旧字段）
    reason: str | None = Field(default=None, max_length=200)  # 原因分类
    competitor: str | None = Field(default=None, max_length=200)
    detail: str | None = None
    improvement: str | None = None


class DealCloseAnalysisOut(BaseModel):
    id: UUID
    deal_id: UUID
    close_type: str
    reason: str | None
    competitor: str | None
    detail: str | None
    improvement: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DealBatchUpdate(BaseModel):
    deal_ids: list[UUID] = Field(min_length=1, max_length=100)
    owner_user_id: UUID | None = None
    stage_id: UUID | None = None
    status: str | None = None


class DealCloneOut(BaseModel):
    source_deal_id: UUID
    deal_id: UUID


class DealOut(BaseModel):
    id: UUID
    tenant_id: UUID
    deal_number: str | None
    title: str
    customer_id: UUID
    contact_id: UUID | None
    pipeline_id: UUID
    stage_id: UUID
    amount: float
    expected_close_date: datetime | None
    probability: int
    status: str
    loss_reason: str | None
    source: str | None
    description: str | None
    next_step: str | None
    deal_type: str | None
    priority: str
    competitor: str | None
    contact_role: str | None
    campaign_id: UUID | None
    owner_user_id: UUID
    territory_id: UUID | None
    lines: list[DealLineItemOut] = Field(default_factory=list)
    converted_from_lead_id: UUID | None
    converted_order_id: UUID | None
    closed_at: datetime | None
    extra_data: dict
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    stage_stay_days: int | None = None
    stage_max_stay_days: int | None = None
    is_stage_overdue: bool = False

    model_config = {"from_attributes": True}


class DealListResponse(BaseModel):
    items: list[DealOut]
    total: int
    page: int
    page_size: int
    list_fields: list[dict] | None = None
    view_id: UUID | None = None
    filters_applied: bool | None = None


class DealStageLogOut(BaseModel):
    id: UUID
    deal_id: UUID
    from_stage_id: UUID | None
    to_stage_id: UUID
    changed_by_user_id: UUID
    changed_at: datetime
    note: str | None

    model_config = {"from_attributes": True}


class DealConvertToOrderOut(BaseModel):
    deal_id: UUID
    order_id: UUID


# ============================================================
# 产品
# ============================================================


class ProductCreate(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    unit: str | None = None
    list_price: float = Field(default=0, ge=0)
    cost_price: float | None = Field(default=None, ge=0)
    category_id: UUID | None = None
    is_active: bool = True
    description: str | None = None
    extra_data: dict = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit: str | None = None
    list_price: float | None = Field(default=None, ge=0)
    cost_price: float | None = Field(default=None, ge=0)
    category_id: UUID | None = None
    is_active: bool | None = None
    description: str | None = None
    extra_data: dict | None = None


class ProductOut(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    unit: str | None
    list_price: float
    cost_price: float | None
    category_id: UUID | None = None
    is_active: bool
    description: str | None
    extra_data: dict
    total_ordered_quantity: int = 0
    total_revenue: float = 0
    last_order_date: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int
    list_fields: list[dict] | None = None
    view_id: UUID | None = None
    filters_applied: bool | None = None


class ProductVariantCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    variant_name: str = Field(min_length=1, max_length=100)
    attributes: dict = Field(default_factory=dict)
    list_price: float = Field(default=0, ge=0)
    cost_price: float | None = Field(default=None, ge=0)
    is_active: bool = True


class ProductVariantUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=50)
    variant_name: str | None = Field(default=None, min_length=1, max_length=100)
    attributes: dict | None = None
    list_price: float | None = Field(default=None, ge=0)
    cost_price: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ProductVariantOut(BaseModel):
    id: UUID
    tenant_id: UUID
    product_id: UUID
    sku: str
    variant_name: str
    attributes: dict
    list_price: float
    cost_price: float | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PriceBookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_default: bool = False
    is_active: bool = True


class PriceBookUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_default: bool | None = None
    is_active: bool | None = None


class PriceBookOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    is_default: bool
    is_active: bool
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PriceBookEntryCreate(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    unit_price: float = Field(ge=0)
    min_quantity: int = Field(default=1, ge=1)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    customer_levels: list[str] | None = None


class PriceBookEntryOut(BaseModel):
    id: UUID
    tenant_id: UUID
    price_book_id: UUID
    product_id: UUID
    variant_id: UUID | None
    unit_price: float
    min_quantity: int
    valid_from: datetime | None
    valid_to: datetime | None
    customer_levels: list | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: UUID | None = None
    description: str | None = Field(default=None, max_length=500)
    sort_order: int = 0
    is_active: bool = True


class ProductCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: UUID | None = None
    description: str | None = Field(default=None, max_length=500)
    sort_order: int | None = None
    is_active: bool | None = None


class ProductCategoryOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    parent_id: UUID | None
    description: str | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 报价 + 报价行
# ============================================================


class QuoteLineCreate(BaseModel):
    product_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    unit: str | None = None
    quantity: float = Field(default=1, ge=0)
    unit_price: float = Field(default=0, ge=0)
    discount_rate: float | None = Field(default=None, ge=0, le=100)
    line_total: float = Field(default=0, ge=0)
    sort_order: int = 0
    remark: str | None = None


class QuoteLineUpdate(BaseModel):
    product_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit: str | None = None
    quantity: float | None = Field(default=None, ge=0)
    unit_price: float | None = Field(default=None, ge=0)
    discount_rate: float | None = Field(default=None, ge=0, le=100)
    line_total: float | None = Field(default=None, ge=0)
    sort_order: int | None = None
    remark: str | None = None


class QuoteLineOut(BaseModel):
    id: UUID
    quote_id: UUID
    product_id: UUID | None
    name: str
    unit: str | None
    quantity: float
    unit_price: float
    discount_rate: float | None
    line_total: float
    sort_order: int
    remark: str | None

    model_config = {"from_attributes": True}


def validate_quote_status(value: str) -> None:
    if value not in QUOTE_STATUSES:
        raise ValueError(f"status 必须是 {QUOTE_STATUSES} 之一")


class QuoteCreate(BaseModel):
    quote_number: str | None = None  # 缺省自动生成
    deal_id: UUID | None = None
    customer_id: UUID
    contact_id: UUID | None = None
    subject: str = Field(min_length=1, max_length=200)
    discount_rate: float | None = Field(default=None, ge=0, le=100)
    total_amount: float = Field(default=0, ge=0)
    status: str = "draft"
    valid_until: datetime | None = None
    owner_user_id: UUID | None = None
    extra_data: dict = Field(default_factory=dict)
    lines: list[QuoteLineCreate] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        validate_quote_status(v)
        return v


class QuoteUpdate(BaseModel):
    deal_id: UUID | None = None
    customer_id: UUID | None = None
    contact_id: UUID | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    discount_rate: float | None = Field(default=None, ge=0, le=100)
    total_amount: float | None = Field(default=None, ge=0)
    status: str | None = None
    valid_until: datetime | None = None
    owner_user_id: UUID | None = None
    extra_data: dict | None = None
    lines: list[QuoteLineCreate] | None = None

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str | None) -> str | None:
        if v is not None:
            validate_quote_status(v)
        return v


class QuoteOut(BaseModel):
    id: UUID
    tenant_id: UUID
    quote_number: str
    deal_id: UUID | None
    customer_id: UUID
    contact_id: UUID | None
    subject: str
    discount_rate: float | None
    total_amount: float
    status: str
    valid_until: datetime | None
    owner_user_id: UUID
    converted_order_id: UUID | None
    extra_data: dict
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    lines: list[QuoteLineOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class QuoteListResponse(BaseModel):
    items: list[QuoteOut]
    total: int
    page: int
    page_size: int
    list_fields: list[dict] | None = None
    view_id: UUID | None = None
    filters_applied: bool | None = None


class QuoteConvertToOrderOut(BaseModel):
    quote_id: UUID
    order_id: UUID


# ============================================================
# 合同
# ============================================================


def validate_contract_status(value: str) -> None:
    if value not in CONTRACT_STATUSES:
        raise ValueError(f"status 必须是 {CONTRACT_STATUSES} 之一")


def validate_contract_type(value: str) -> None:
    if value not in CONTRACT_TYPES:
        raise ValueError(f"contract_type 必须是 {CONTRACT_TYPES} 之一")


class ContractCreate(BaseModel):
    contract_number: str | None = None
    deal_id: UUID | None = None
    customer_id: UUID
    quote_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    contract_type: str = "new"
    amount: float = Field(default=0, ge=0)
    signed_amount: float | None = Field(default=None, ge=0)
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str = "draft"
    owner_user_id: UUID | None = None
    file_url: str | None = None
    extra_data: dict = Field(default_factory=dict)

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        validate_contract_status(v)
        return v

    @field_validator("contract_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        validate_contract_type(v)
        return v


class ContractTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=50)
    content: str = Field(min_length=1)
    variables: list[str] = Field(default_factory=list)
    is_active: bool = True


class ContractTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=50)
    content: str | None = Field(default=None, min_length=1)
    variables: list[str] | None = None
    is_active: bool | None = None


class ContractTemplateOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    category: str | None
    content: str
    variables: list
    is_active: bool
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContractFromTemplateRequest(BaseModel):
    template_id: UUID
    customer_id: UUID
    deal_id: UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    contract_type: str = "new"
    amount: float | None = Field(default=None, ge=0)
    start_date: datetime | None = None
    end_date: datetime | None = None
    variable_values: dict = Field(default_factory=dict)
    extra_data: dict = Field(default_factory=dict)

    @field_validator("contract_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        validate_contract_type(v)
        return v


class ContractUpdate(BaseModel):
    deal_id: UUID | None = None
    customer_id: UUID | None = None
    quote_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    contract_type: str | None = None
    amount: float | None = Field(default=None, ge=0)
    signed_amount: float | None = Field(default=None, ge=0)
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = None
    owner_user_id: UUID | None = None
    file_url: str | None = None
    extra_data: dict | None = None

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str | None) -> str | None:
        if v is not None:
            validate_contract_status(v)
        return v

    @field_validator("contract_type")
    @classmethod
    def _valid_type(cls, v: str | None) -> str | None:
        if v is not None:
            validate_contract_type(v)
        return v


class ContractOut(BaseModel):
    id: UUID
    tenant_id: UUID
    contract_number: str
    deal_id: UUID | None
    customer_id: UUID
    quote_id: UUID | None
    title: str
    contract_type: str
    amount: float
    signed_amount: float | None
    start_date: datetime | None
    end_date: datetime | None
    status: str
    signed_at: datetime | None
    owner_user_id: UUID
    file_url: str | None
    extra_data: dict
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContractListResponse(BaseModel):
    items: list[ContractOut]
    total: int
    page: int
    page_size: int
    list_fields: list[dict] | None = None
    view_id: UUID | None = None
    filters_applied: bool | None = None


class ContractConvertToOrderOut(BaseModel):
    contract_id: UUID
    order_id: UUID


# ============================================================
# 订单 + 订单行
# ============================================================


class OrderLineCreate(BaseModel):
    product_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    unit: str | None = None
    quantity: float = Field(default=1, ge=0)
    unit_price: float = Field(default=0, ge=0)
    discount_rate: float | None = Field(default=None, ge=0, le=100)
    tax_rate: float | None = Field(default=None, ge=0, le=100)
    tax_amount: float | None = Field(default=None, ge=0)
    line_total: float = Field(default=0, ge=0)
    sort_order: int = 0
    remark: str | None = None


class OrderLineOut(BaseModel):
    id: UUID
    order_id: UUID
    product_id: UUID | None
    name: str
    unit: str | None
    quantity: float
    unit_price: float
    discount_rate: float | None
    tax_rate: float | None
    tax_amount: float | None
    line_total: float
    sort_order: int
    remark: str | None

    model_config = {"from_attributes": True}


def validate_order_status(value: str) -> None:
    if value not in ORDER_STATUSES:
        raise ValueError(f"status 必须是 {ORDER_STATUSES} 之一")


def validate_order_source(value: str) -> None:
    if value not in ORDER_SOURCES:
        raise ValueError(f"source 必须是 {ORDER_SOURCES} 之一")


class OrderCreate(BaseModel):
    order_number: str | None = None
    title: str = Field(min_length=1, max_length=200)
    customer_id: UUID
    contact_id: UUID | None = None
    deal_id: UUID | None = None
    quote_id: UUID | None = None
    contract_id: UUID | None = None
    source: str = "deal"
    order_date: datetime | None = None
    amount: float = Field(default=0, ge=0)
    status: str = "draft"
    owner_user_id: UUID | None = None
    territory_id: UUID | None = None
    extra_data: dict = Field(default_factory=dict)
    lines: list[OrderLineCreate] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        validate_order_status(v)
        return v

    @field_validator("source")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        validate_order_source(v)
        return v


class OrderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    customer_id: UUID | None = None
    contact_id: UUID | None = None
    deal_id: UUID | None = None
    quote_id: UUID | None = None
    contract_id: UUID | None = None
    source: str | None = None
    order_date: datetime | None = None
    amount: float | None = Field(default=None, ge=0)
    status: str | None = None
    owner_user_id: UUID | None = None
    territory_id: UUID | None = None
    extra_data: dict | None = None
    lines: list[OrderLineCreate] | None = None

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str | None) -> str | None:
        if v is not None:
            validate_order_status(v)
        return v

    @field_validator("source")
    @classmethod
    def _valid_source(cls, v: str | None) -> str | None:
        if v is not None:
            validate_order_source(v)
        return v


class OrderOut(BaseModel):
    id: UUID
    tenant_id: UUID
    order_number: str
    title: str
    customer_id: UUID
    contact_id: UUID | None
    deal_id: UUID | None
    quote_id: UUID | None
    contract_id: UUID | None
    source: str
    order_date: datetime
    amount: float
    status: str
    parent_order_id: UUID | None = None
    version: int = 1
    revision_reason: str | None = None
    owner_user_id: UUID
    territory_id: UUID | None
    extra_data: dict
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    lines: list[OrderLineOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    page_size: int
    list_fields: list[dict] | None = None
    view_id: UUID | None = None
    filters_applied: bool | None = None


class OrderRejectBody(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class OrderReviseBody(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    lines: list[OrderLineCreate] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)


class OrderApprovalRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    min_amount: float = Field(ge=0)
    max_amount: float | None = Field(default=None, ge=0)
    approver_role: str = Field(default="sales_manager", min_length=1, max_length=50)
    approval_type: str = Field(default="sequential", pattern="^(sequential|any)$")
    is_active: bool = True


class OrderApprovalRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    min_amount: float | None = Field(default=None, ge=0)
    max_amount: float | None = Field(default=None, ge=0)
    approver_role: str | None = Field(default=None, min_length=1, max_length=50)
    approval_type: str | None = Field(default=None, pattern="^(sequential|any)$")
    is_active: bool | None = None


class OrderApprovalRuleOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    min_amount: float
    max_amount: float | None
    approver_role: str
    approval_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApprovalInstanceOut(BaseModel):
    id: UUID
    tenant_id: UUID
    entity_type: str
    entity_id: UUID
    rule_id: UUID | None
    status: str
    current_step: int
    steps_json: list
    submitted_by_user_id: UUID
    submitted_at: datetime | None
    resolved_at: datetime | None
    reject_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 回款计划 + 回款
# ============================================================


class PaymentPlanCreate(BaseModel):
    installment_no: int = Field(ge=1)
    plan_date: datetime
    plan_amount: float = Field(default=0, ge=0)
    remark: str | None = None


class PaymentPlanOut(BaseModel):
    id: UUID
    order_id: UUID
    installment_no: int
    plan_date: datetime
    plan_amount: float
    remark: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


def validate_payment_status(value: str) -> None:
    if value not in PAYMENT_STATUSES:
        raise ValueError(f"status 必须是 {PAYMENT_STATUSES} 之一")


def validate_payment_method(value: str) -> None:
    if value not in PAYMENT_METHODS:
        raise ValueError(f"method 必须是 {PAYMENT_METHODS} 之一")


class PaymentCreate(BaseModel):
    order_id: UUID
    payment_number: str | None = None
    plan_id: UUID | None = None
    amount: float = Field(ge=0)
    paid_at: datetime | None = None
    method: str = "bank"
    status: str = "pending"
    remark: str | None = None
    owner_user_id: UUID | None = None

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        validate_payment_status(v)
        return v

    @field_validator("method")
    @classmethod
    def _valid_method(cls, v: str) -> str:
        validate_payment_method(v)
        return v


class PaymentUpdate(BaseModel):
    amount: float | None = Field(default=None, ge=0)
    paid_at: datetime | None = None
    method: str | None = None
    status: str | None = None
    remark: str | None = None
    owner_user_id: UUID | None = None

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str | None) -> str | None:
        if v is not None:
            validate_payment_status(v)
        return v

    @field_validator("method")
    @classmethod
    def _valid_method(cls, v: str | None) -> str | None:
        if v is not None:
            validate_payment_method(v)
        return v


class PaymentOut(BaseModel):
    id: UUID
    tenant_id: UUID
    order_id: UUID
    payment_number: str
    plan_id: UUID | None
    amount: float
    paid_at: datetime
    method: str
    status: str
    remark: str | None
    owner_user_id: UUID
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    # 列表汇总（订单维度，可选）
    order_plan_total: float | None = None
    order_paid_total: float | None = None
    order_overdue_amount: float | None = None

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    items: list[PaymentOut]
    total: int
    page: int
    page_size: int
    list_fields: list[dict] | None = None
    view_id: UUID | None = None
    filters_applied: bool | None = None


# ============================================================
# 发货 / 发票（v1.0 P1）
# ============================================================


def validate_delivery_status(value: str) -> None:
    if value not in DELIVERY_NOTE_STATUSES:
        raise ValueError(f"status 必须是 {DELIVERY_NOTE_STATUSES} 之一")


def validate_invoice_type(value: str) -> None:
    if value not in INVOICE_TYPES:
        raise ValueError(f"invoice_type 必须是 {INVOICE_TYPES} 之一")


def validate_invoice_status(value: str) -> None:
    if value not in INVOICE_STATUSES:
        raise ValueError(f"status 必须是 {INVOICE_STATUSES} 之一")


class DeliveryItemCreate(BaseModel):
    order_line_id: UUID
    quantity: float = Field(gt=0)


class DeliveryItemOut(BaseModel):
    id: UUID
    tenant_id: UUID
    delivery_note_id: UUID
    order_line_id: UUID
    quantity: float

    model_config = {"from_attributes": True}


class DeliveryCreate(BaseModel):
    tracking_number: str | None = Field(default=None, max_length=100)
    carrier: str | None = Field(default=None, max_length=50)
    remark: str | None = Field(default=None, max_length=500)
    items: list[DeliveryItemCreate] = Field(default_factory=list)


class DeliveryUpdate(BaseModel):
    tracking_number: str | None = Field(default=None, max_length=100)
    carrier: str | None = Field(default=None, max_length=50)
    remark: str | None = Field(default=None, max_length=500)
    status: str | None = None

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str | None) -> str | None:
        if v is not None:
            validate_delivery_status(v)
        return v


class DeliveryOut(BaseModel):
    id: UUID
    tenant_id: UUID
    order_id: UUID
    delivery_number: str
    status: str
    shipped_at: datetime | None
    delivered_at: datetime | None
    tracking_number: str | None
    carrier: str | None
    remark: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    items: list[DeliveryItemOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class InvoiceCreate(BaseModel):
    invoice_type: str = "vat"
    amount: float = Field(ge=0)
    tax_amount: float = Field(default=0, ge=0)
    total_amount: float | None = Field(default=None, ge=0)
    extra_data: dict = Field(default_factory=dict)

    @field_validator("invoice_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        validate_invoice_type(v)
        return v


class InvoiceUpdate(BaseModel):
    invoice_type: str | None = None
    amount: float | None = Field(default=None, ge=0)
    tax_amount: float | None = Field(default=None, ge=0)
    total_amount: float | None = Field(default=None, ge=0)
    extra_data: dict | None = None

    @field_validator("invoice_type")
    @classmethod
    def _valid_type(cls, v: str | None) -> str | None:
        if v is not None:
            validate_invoice_type(v)
        return v


class InvoiceOut(BaseModel):
    id: UUID
    tenant_id: UUID
    order_id: UUID
    invoice_number: str
    invoice_type: str
    amount: float
    tax_amount: float
    total_amount: float
    status: str
    issued_at: datetime | None
    extra_data: dict
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvoicePaymentCreate(BaseModel):
    payment_id: UUID
    matched_amount: float = Field(gt=0)


class InvoicePaymentOut(BaseModel):
    invoice_id: UUID
    payment_id: UUID
    matched_amount: float
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 合同补充协议 / 退款 / 应收（v1.0 P1 D-F）
# ============================================================


class ContractAmendmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    change_type: str = "amount_change"
    original_value: str | None = None
    new_value: str | None = None
    amount_delta: float | None = None

    @field_validator("change_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in CONTRACT_AMENDMENT_CHANGE_TYPES:
            raise ValueError(f"change_type 必须是 {CONTRACT_AMENDMENT_CHANGE_TYPES} 之一")
        return v


class ContractAmendmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    change_type: str | None = None
    original_value: str | None = None
    new_value: str | None = None
    amount_delta: float | None = None
    status: str | None = None

    @field_validator("change_type")
    @classmethod
    def _valid_type(cls, v: str | None) -> str | None:
        if v is not None and v not in CONTRACT_AMENDMENT_CHANGE_TYPES:
            raise ValueError(f"change_type 无效")
        return v

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str | None) -> str | None:
        if v is not None and v not in CONTRACT_AMENDMENT_STATUSES:
            raise ValueError(f"status 无效")
        return v


class ContractAmendmentOut(BaseModel):
    id: UUID
    tenant_id: UUID
    parent_contract_id: UUID
    amendment_number: str
    title: str
    change_type: str
    original_value: str | None
    new_value: str | None
    amount_delta: float | None
    status: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContractRenewOut(BaseModel):
    contract_id: UUID
    deal_id: UUID


class RefundCreate(BaseModel):
    order_id: UUID
    original_payment_id: UUID | None = None
    amount: float = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)


class RefundOut(BaseModel):
    id: UUID
    tenant_id: UUID
    order_id: UUID
    original_payment_id: UUID | None
    refund_number: str
    amount: float
    reason: str | None
    status: str
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReceivableItemOut(BaseModel):
    order_id: UUID
    order_number: str | None = None
    order_title: str | None = None
    plan_id: UUID
    installment_no: int
    plan_date: datetime
    plan_amount: float
    paid_amount: float
    outstanding: float
    days_overdue: int
    aging_bucket: str  # current | d30 | d60 | d90plus


class ReceivableSummaryOut(BaseModel):
    items: list[ReceivableItemOut]
    buckets: dict[str, float]
    total_outstanding: float


# ---------------- 实体自动编号规则（v0.8） ----------------

ENTITY_NUMBER_TYPES = (
    "lead", "customer", "task", "campaign", "deal",
    "quote", "contract", "order", "payment", "product",
)
RESET_PERIODS = ("once", "daily", "weekly", "monthly", "yearly")


class EntityNumberRuleOut(BaseModel):
    entity_type: str
    prefix: str
    date_format: str
    seq_width: int
    reset_period: str
    enabled: bool


class EntityNumberRuleUpdate(BaseModel):
    prefix: str | None = Field(default=None, max_length=10)
    date_format: str | None = Field(default=None, max_length=20)
    seq_width: int | None = Field(default=None, ge=1, le=8)
    reset_period: str | None = None
    enabled: bool | None = None

    @field_validator("reset_period")
    @classmethod
    def _check_reset_period(cls, v: str | None) -> str | None:
        if v is not None and v not in RESET_PERIODS:
            raise ValueError("非法重置周期")
        return v


# 重新导出常用常量，供 routers 复用
__all__ = [
    "CONTRACT_STATUSES",
    "CONTRACT_TYPES",
    "DEAL_SOURCES",
    "DEAL_STATUSES",
    "ORDER_SOURCES",
    "ORDER_STATUSES",
    "PAYMENT_METHODS",
    "PAYMENT_STATUSES",
    "QUOTE_STATUSES",
    "PipelineCreate",
    "PipelineOut",
    "PipelineStageCreate",
    "PipelineStageOut",
    "PipelineStageUpdate",
    "PipelineUpdate",
    "DealClose",
    "DealConvertToOrderOut",
    "DealCreate",
    "DealListResponse",
    "DealOut",
    "DealStageChange",
    "DealStageLogOut",
    "DealUpdate",
    "ProductCreate",
    "ProductUpdate",
    "ProductOut",
    "ProductListResponse",
    "QuoteLineCreate",
    "QuoteLineUpdate",
    "QuoteLineOut",
    "QuoteCreate",
    "QuoteUpdate",
    "QuoteOut",
    "QuoteListResponse",
    "QuoteConvertToOrderOut",
    "ContractCreate",
    "ContractUpdate",
    "ContractOut",
    "ContractListResponse",
    "ContractConvertToOrderOut",
    "OrderLineCreate",
    "OrderLineOut",
    "OrderCreate",
    "OrderUpdate",
    "OrderOut",
    "OrderListResponse",
    "OrderRejectBody",
    "OrderReviseBody",
    "OrderApprovalRuleCreate",
    "OrderApprovalRuleUpdate",
    "OrderApprovalRuleOut",
    "ApprovalInstanceOut",
    "PaymentPlanCreate",
    "PaymentPlanOut",
    "PaymentCreate",
    "PaymentUpdate",
    "PaymentOut",
    "PaymentListResponse",
    "DeliveryItemCreate",
    "DeliveryItemOut",
    "DeliveryCreate",
    "DeliveryUpdate",
    "DeliveryOut",
    "InvoiceCreate",
    "InvoiceUpdate",
    "InvoiceOut",
    "InvoicePaymentCreate",
    "InvoicePaymentOut",
    "ContractAmendmentCreate",
    "ContractAmendmentUpdate",
    "ContractAmendmentOut",
    "ContractRenewOut",
    "RefundCreate",
    "RefundOut",
    "ReceivableItemOut",
    "ReceivableSummaryOut",
    "ProductVariantCreate",
    "ProductVariantUpdate",
    "ProductVariantOut",
    "PriceBookCreate",
    "PriceBookUpdate",
    "PriceBookOut",
    "PriceBookEntryCreate",
    "PriceBookEntryOut",
    "EntityNumberRuleOut",
    "EntityNumberRuleUpdate",
    "ENTITY_NUMBER_TYPES",
    "RESET_PERIODS",
]
