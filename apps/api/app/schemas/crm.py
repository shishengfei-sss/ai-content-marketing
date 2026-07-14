"""CRM API Schemas。"""
from __future__ import annotations

import re
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.crm import (
    ACTIVITY_TYPES,
    CAMPAIGN_STATUSES,
    CUSTOMER_STATUSES,
    LEAD_STATUSES,
    TASK_PRIORITIES,
    TASK_STATUSES,
)

LEAD_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")
_EXCEL_MOBILE_DECIMAL_RE = re.compile(r"^\d+\.0+$")
_EXCEL_MOBILE_SCI_RE = re.compile(r"^[\d.]+e[+-]?\d+$", re.I)


def coerce_mobile_raw(value: object) -> str:
    """兼容 Excel 导入：浮点、科学计数法、+86 前缀等。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:  # NaN
            return ""
        rounded = round(value)
        if abs(value - rounded) < 1e-6:
            return str(int(rounded))
        return str(value).strip()

    s = str(value).strip().replace("\ufeff", "").replace(",", "").replace(" ", "")
    if not s:
        return ""
    if s.startswith("+86"):
        s = s[3:].lstrip()
    elif s.startswith("86") and len(s) == 13 and s[2:].isdigit():
        s = s[2:]
    if _EXCEL_MOBILE_DECIMAL_RE.match(s):
        s = s.split(".", 1)[0]
    elif _EXCEL_MOBILE_SCI_RE.match(s):
        try:
            n = float(s)
            if abs(n - round(n)) < 1e-6:
                s = str(int(round(n)))
        except ValueError:
            pass
    return s


def validate_lead_mobile_value(value: str | None, *, required: bool = True) -> tuple[str | None, str | None]:
    """返回 (规范化手机号, 错误信息)。"""
    mobile = coerce_mobile_raw(value)
    if not mobile:
        if required:
            return None, "手机不能为空"
        return None, None
    if not LEAD_MOBILE_RE.match(mobile):
        return None, "手机格式无效"
    return mobile, None


def normalize_lead_mobile(value: str | None, *, required: bool = True) -> str:
    mobile, err = validate_lead_mobile_value(value, required=required)
    if err:
        raise ValueError(err)
    assert mobile is not None
    return mobile


class LeadCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    contact_name: str = Field(min_length=1, max_length=100)
    mobile: str = Field(min_length=1, max_length=11)
    phone: str | None = None
    email: str | None = None
    source: str | None = None
    source_detail: str | None = Field(default=None, max_length=200)
    utm_source: str | None = Field(default=None, max_length=100)
    utm_medium: str | None = Field(default=None, max_length=100)
    utm_campaign: str | None = Field(default=None, max_length=100)
    landing_url: str | None = Field(default=None, max_length=500)
    acquisition_cost: float | None = Field(default=None, ge=0)
    title: str | None = Field(default=None, max_length=100)
    lead_score: int | None = Field(default=None, ge=0, le=100)
    department: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default="中国", max_length=50)
    status: str = "待跟进"
    remark: str | None = None
    extra_data: dict = Field(default_factory=dict)
    campaign_id: UUID | None = None
    territory_id: UUID | None = None

    @field_validator("mobile", mode="before")
    @classmethod
    def _strip_mobile(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()

    @field_validator("contact_name", mode="before")
    @classmethod
    def _strip_contact_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()

    @field_validator("contact_name")
    @classmethod
    def _valid_contact_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("联系人姓名不能为空")
        return value.strip()

    @field_validator("mobile")
    @classmethod
    def _valid_mobile(cls, value: str) -> str:
        return normalize_lead_mobile(value, required=True)


class LeadUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_name: str | None = None
    mobile: str | None = None
    phone: str | None = None
    email: str | None = None
    source: str | None = None
    source_detail: str | None = Field(default=None, max_length=200)
    utm_source: str | None = Field(default=None, max_length=100)
    utm_medium: str | None = Field(default=None, max_length=100)
    utm_campaign: str | None = Field(default=None, max_length=100)
    landing_url: str | None = Field(default=None, max_length=500)
    acquisition_cost: float | None = Field(default=None, ge=0)
    title: str | None = Field(default=None, max_length=100)
    lead_score: int | None = Field(default=None, ge=0, le=100)
    department: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=50)
    status: str | None = None
    owner_user_id: UUID | None = None
    remark: str | None = None
    extra_data: dict | None = None
    campaign_id: UUID | None = None
    territory_id: UUID | None = None

    @field_validator("mobile", mode="before")
    @classmethod
    def _strip_mobile(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()

    @field_validator("mobile")
    @classmethod
    def _valid_mobile(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_lead_mobile(value, required=True)


class LeadOut(BaseModel):
    id: UUID
    lead_number: str | None
    company_name: str
    contact_name: str | None
    mobile: str | None
    phone: str | None
    email: str | None
    source: str | None
    source_detail: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    landing_url: str | None = None
    acquisition_cost: float | None = None
    title: str | None = None
    lead_score: int | None = None
    department: str | None = None
    country: str | None = None
    status: str
    owner_user_id: UUID | None = None
    pool_id: UUID | None = None
    claimed_at: datetime | None = None
    territory_id: UUID | None = None
    campaign_id: UUID | None = None
    next_follow_up_at: datetime | None = None
    remark: str | None
    converted_customer_id: UUID | None = None
    extra_data: dict
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    items: list[LeadOut]
    total: int
    page: int
    page_size: int
    list_fields: list[dict] | None = None
    view_id: UUID | None = None
    filters_applied: bool | None = None


class CustomerCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    mobile: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str = "潜在"
    description: str | None = Field(default=None, max_length=2000)
    type: str | None = Field(default="客户", max_length=20)
    parent_customer_id: UUID | None = None
    tags: list[str] | None = None
    source: str | None = Field(default=None, max_length=50)
    remark: str | None = None
    extra_data: dict = Field(default_factory=dict)

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, value: object) -> list[str] | None:
        if value is None or value == "":
            return None
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            parts = value.replace("，", ",").split(",")
            return [p.strip() for p in parts if p.strip()]
        return None


class CustomerUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    mobile: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str | None = None
    owner_user_id: UUID | None = None
    description: str | None = Field(default=None, max_length=2000)
    type: str | None = Field(default=None, max_length=20)
    parent_customer_id: UUID | None = None
    tags: list[str] | None = None
    source: str | None = Field(default=None, max_length=50)
    remark: str | None = None
    extra_data: dict | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, value: object) -> list[str] | None:
        if value is None or value == "":
            return None
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            parts = value.replace("，", ",").split(",")
            return [p.strip() for p in parts if p.strip()]
        return None


class CustomerOut(BaseModel):
    id: UUID
    customer_number: str | None
    company_name: str
    mobile: str | None
    phone: str | None
    email: str | None
    status: str
    description: str | None = None
    type: str | None = None
    parent_customer_id: UUID | None = None
    total_revenue: float | None = None
    last_deal_date: date | None = None
    tags: list | None = None
    source: str | None = None
    converted_lead_score: int | None = None
    owner_user_id: UUID | None = None
    pool_id: UUID | None = None
    claimed_at: datetime | None = None
    converted_from_lead_id: UUID | None
    remark: str | None
    extra_data: dict
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    items: list[CustomerOut]
    total: int
    page: int
    page_size: int
    list_fields: list[dict] | None = None
    view_id: UUID | None = None


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    mobile: str | None = None
    phone: str | None = None
    email: str | None = None
    wechat: str | None = None
    title: str | None = None
    department: str | None = None
    is_primary: bool = False
    contact_role: str | None = None
    reports_to_contact_id: UUID | None = None
    remark: str | None = None
    extra_data: dict = Field(default_factory=dict)


class ContactOut(BaseModel):
    id: UUID
    customer_id: UUID
    name: str
    mobile: str | None
    phone: str | None
    email: str | None
    wechat: str | None
    title: str | None
    department: str | None
    is_primary: bool
    contact_role: str | None = None
    reports_to_contact_id: UUID | None = None
    remark: str | None
    extra_data: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ActivityCreate(BaseModel):
    lead_id: UUID | None = None
    customer_id: UUID | None = None
    deal_id: UUID | None = None
    activity_type: str
    subject: str | None = Field(default=None, max_length=200)
    content: str = ""
    next_follow_up_at: datetime | None = None
    status: str | None = None


class ActivityUpdate(BaseModel):
    activity_type: str | None = None
    subject: str | None = Field(default=None, max_length=200)
    content: str | None = None


class ActivityOut(BaseModel):
    id: UUID
    lead_id: UUID | None
    customer_id: UUID | None
    deal_id: UUID | None
    activity_type: str
    subject: str | None
    content: str
    entity_type: str | None
    entity_id: str | None
    created_by_user_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


def validate_lead_status(status: str) -> None:
    if status not in LEAD_STATUSES:
        raise ValueError(f"status 必须是 {LEAD_STATUSES} 之一")


def validate_customer_status(status: str) -> None:
    if status not in CUSTOMER_STATUSES:
        raise ValueError(f"status 必须是 {CUSTOMER_STATUSES} 之一")


def validate_activity_type(activity_type: str) -> None:
    if activity_type not in ACTIVITY_TYPES:
        raise ValueError(f"activity_type 必须是 {ACTIVITY_TYPES} 之一")


class AttachmentOut(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    file_name: str
    file_size: int
    file_type: str | None
    uploaded_by_user_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class TerritoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    parent_id: UUID | None = None
    manager_membership_id: UUID | None = None
    sort_order: int = 0
    is_active: bool = True


class TerritoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)
    parent_id: UUID | None = None
    manager_membership_id: UUID | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class TerritoryOut(BaseModel):
    id: UUID
    tenant_id: UUID
    parent_id: UUID | None
    name: str
    code: str | None
    manager_membership_id: UUID | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SalesProfileUpdate(BaseModel):
    primary_territory_id: UUID | None = None
    reports_to_membership_id: UUID | None = None


class SalesProfileOut(BaseModel):
    membership_id: UUID
    user_id: UUID
    display_name: str | None
    phone: str | None
    role_name: str | None
    primary_territory_id: UUID | None
    reports_to_membership_id: UUID | None

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: str = "open"
    priority: str = "normal"
    planned_start_at: datetime | None = None
    started_at: datetime | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    assignee_user_id: UUID | None = None
    territory_id: UUID | None = None
    lead_id: UUID | None = None
    customer_id: UUID | None = None
    campaign_id: UUID | None = None
    content_id: UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    planned_start_at: datetime | None = None
    started_at: datetime | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    assignee_user_id: UUID | None = None
    territory_id: UUID | None = None
    lead_id: UUID | None = None
    customer_id: UUID | None = None
    campaign_id: UUID | None = None


class TaskOut(BaseModel):
    id: UUID
    task_number: str | None
    title: str
    description: str | None
    status: str
    priority: str
    planned_start_at: datetime | None
    started_at: datetime | None
    due_at: datetime | None
    completed_at: datetime | None
    assignee_user_id: UUID
    owner_user_id: UUID
    territory_id: UUID | None
    lead_id: UUID | None
    customer_id: UUID | None
    campaign_id: UUID | None
    content_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskOut]
    total: int
    page: int
    page_size: int


class LeadConvertRequest(BaseModel):
    create_deal: bool = False
    deal_title: str | None = Field(default=None, max_length=200)
    deal_amount: float | None = None
    deal_pipeline_id: UUID | None = None
    deal_stage_id: UUID | None = None
    merge_into_customer_id: UUID | None = None
    # 默认 True 保持旧行为不破坏已有转化；去重检测时显式传 False
    force_create: bool = False


class LeadConvertOut(BaseModel):
    lead_id: UUID
    customer_id: UUID
    contact_id: UUID | None
    deal_id: UUID | None = None
    merged: bool = False
    duplicate_candidates: list[UUID] | None = None


def validate_task_status(status: str) -> None:
    if status not in TASK_STATUSES:
        raise ValueError(f"status 必须是 {TASK_STATUSES} 之一")


def validate_task_priority(priority: str) -> None:
    if priority not in TASK_PRIORITIES:
        raise ValueError(f"priority 必须是 {TASK_PRIORITIES} 之一")


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    status: str = "draft"
    start_at: datetime | None = None
    end_at: datetime | None = None
    goal: str | None = None
    channels: list[str] = Field(default_factory=list)
    description: str | None = None
    territory_id: UUID | None = None


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    goal: str | None = None
    channels: list[str] | None = None
    description: str | None = None
    owner_user_id: UUID | None = None
    territory_id: UUID | None = None


class CampaignOut(BaseModel):
    id: UUID
    campaign_number: str | None
    name: str
    status: str
    start_at: datetime | None
    end_at: datetime | None
    goal: str | None
    channels: list
    description: str | None
    owner_user_id: UUID
    territory_id: UUID | None
    created_at: datetime
    updated_at: datetime
    lead_count: int = 0
    task_count: int = 0
    content_count: int = 0

    model_config = {"from_attributes": True}


class CampaignListResponse(BaseModel):
    items: list[CampaignOut]
    total: int
    page: int
    page_size: int


class CampaignContentLink(BaseModel):
    content_id: UUID


class LeadPoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    territory_id: UUID | None = None
    industry_filter: str | None = None
    auto_reclaim_days: int | None = Field(default=None, ge=1)


class LeadPoolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    territory_id: UUID | None = None
    industry_filter: str | None = None
    auto_reclaim_days: int | None = Field(default=None, ge=1)


class LeadPoolOut(BaseModel):
    id: UUID
    name: str
    territory_id: UUID | None = None
    industry_filter: str | None = None
    auto_reclaim_days: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadPoolClaimRequest(BaseModel):
    lead_id: UUID


class LeadReclaimRequest(BaseModel):
    pool_id: UUID


class CustomerPoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    territory_id: UUID | None = None
    industry_filter: str | None = None
    auto_reclaim_days: int | None = Field(default=None, ge=1)


class CustomerPoolOut(BaseModel):
    id: UUID
    name: str
    territory_id: UUID | None = None
    industry_filter: str | None = None
    auto_reclaim_days: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerPoolClaimRequest(BaseModel):
    customer_id: UUID


class CustomerReclaimRequest(BaseModel):
    pool_id: UUID


class LeadScoringRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    condition_json: dict
    score_value: int = Field(ge=-100, le=100)
    priority: int = 0
    is_active: bool = True


class LeadScoringRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    condition_json: dict | None = None
    score_value: int | None = Field(default=None, ge=-100, le=100)
    priority: int | None = None
    is_active: bool | None = None


class LeadScoringRuleOut(BaseModel):
    id: UUID
    name: str
    condition_json: dict
    score_value: int
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssignmentRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    condition_json: dict = Field(default_factory=dict)
    assign_type: str = "fixed_user"
    target_id: UUID | None = None
    priority: int = 0
    is_active: bool = True


class AssignmentRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    condition_json: dict | None = None
    assign_type: str | None = None
    target_id: UUID | None = None
    priority: int | None = None
    is_active: bool | None = None


class AssignmentRuleOut(BaseModel):
    id: UUID
    name: str
    condition_json: dict
    assign_type: str
    target_id: UUID | None = None
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NurtureRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    condition_json: dict = Field(default_factory=dict)
    action_type: str = "create_task"
    action_config: dict = Field(default_factory=dict)
    priority: int = 0
    is_active: bool = True


class NurtureRuleOut(BaseModel):
    id: UUID
    name: str
    condition_json: dict
    action_type: str
    action_config: dict
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AddressCreate(BaseModel):
    entity_type: str
    entity_id: UUID
    address: str = Field(min_length=1, max_length=300)
    address_type: str = "office"
    is_default: bool = False
    province: str | None = None
    city: str | None = None
    district: str | None = None
    zip_code: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None


class AddressUpdate(BaseModel):
    address: str | None = Field(default=None, min_length=1, max_length=300)
    address_type: str | None = None
    is_default: bool | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None
    zip_code: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None


class AddressOut(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    address_type: str
    is_default: bool
    province: str | None = None
    city: str | None = None
    district: str | None = None
    address: str
    zip_code: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str | None = None
    category: str | None = None


class TagOut(BaseModel):
    id: UUID
    name: str
    color: str | None = None
    category: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EntityTagBind(BaseModel):
    entity_type: str
    entity_id: UUID
    tag_id: UUID | None = None
    tag_name: str | None = None


class EntityTagOut(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    tag_id: UUID
    tag_name: str | None = None
    created_at: datetime


class EntityTeamMemberAdd(BaseModel):
    entity_type: str
    entity_id: UUID
    user_id: UUID
    role: str = "member"


class EntityTeamMemberOut(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    user_id: UUID
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class BantEvaluationCreate(BaseModel):
    budget_score: int = Field(ge=1, le=5)
    authority_score: int = Field(ge=1, le=5)
    need_score: int = Field(ge=1, le=5)
    time_score: int = Field(ge=1, le=5)
    note: str | None = None


class BantEvaluationOut(BaseModel):
    id: UUID
    lead_id: UUID
    budget_score: int
    authority_score: int
    need_score: int
    time_score: int
    total_score: float
    note: str | None = None
    created_by_user_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


def validate_campaign_status(status: str) -> None:
    if status not in CAMPAIGN_STATUSES:
        raise ValueError(f"status 必须是 {CAMPAIGN_STATUSES} 之一")
