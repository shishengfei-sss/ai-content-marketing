"""CRM-2/3 v0.7 Pydantic Schemas（商机/管道/产品/报价/合同/订单/收款）。

Phase B 仅实现 deal + pipeline；其它实体 schema 在后续 Phase 中按需扩展。
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.crm import (
    CONTRACT_STATUSES,
    CONTRACT_TYPES,
    DEAL_SOURCES,
    DEAL_STATUSES,
    ORDER_SOURCES,
    ORDER_STATUSES,
    PAYMENT_METHODS,
    PAYMENT_STATUSES,
    QUOTE_STATUSES,
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
    is_active: bool = True
    description: str | None = None
    extra_data: dict = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit: str | None = None
    list_price: float | None = Field(default=None, ge=0)
    cost_price: float | None = Field(default=None, ge=0)
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
    is_active: bool
    description: str | None
    extra_data: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int
    list_fields: list[dict] | None = None
    filters_applied: bool | None = None


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

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    items: list[PaymentOut]
    total: int
    page: int
    page_size: int
    list_fields: list[dict] | None = None
    view_id: UUID | None = None
    filters_applied: bool | None = None


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
    "PaymentPlanCreate",
    "PaymentPlanOut",
    "PaymentCreate",
    "PaymentUpdate",
    "PaymentOut",
    "PaymentListResponse",
    "EntityNumberRuleOut",
    "EntityNumberRuleUpdate",
    "ENTITY_NUMBER_TYPES",
    "RESET_PERIODS",
]
