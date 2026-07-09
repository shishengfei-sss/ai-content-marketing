"""CRM API Schemas。"""
from __future__ import annotations

import re
from datetime import datetime
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
    company_name: str
    contact_name: str | None
    mobile: str | None
    phone: str | None
    email: str | None
    source: str | None
    status: str
    owner_user_id: UUID
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
    remark: str | None = None
    extra_data: dict = Field(default_factory=dict)


class CustomerUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    mobile: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str | None = None
    owner_user_id: UUID | None = None
    remark: str | None = None
    extra_data: dict | None = None


class CustomerOut(BaseModel):
    id: UUID
    company_name: str
    mobile: str | None
    phone: str | None
    email: str | None
    status: str
    owner_user_id: UUID
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
    is_decision_maker: bool = False
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
    is_decision_maker: bool
    remark: str | None
    extra_data: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ActivityCreate(BaseModel):
    lead_id: UUID | None = None
    customer_id: UUID | None = None
    activity_type: str
    content: str = ""
    next_follow_up_at: datetime | None = None
    status: str | None = None


class ActivityOut(BaseModel):
    id: UUID
    lead_id: UUID | None
    customer_id: UUID | None
    activity_type: str
    content: str
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


class LeadConvertOut(BaseModel):
    lead_id: UUID
    customer_id: UUID
    contact_id: UUID | None


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


def validate_campaign_status(status: str) -> None:
    if status not in CAMPAIGN_STATUSES:
        raise ValueError(f"status 必须是 {CAMPAIGN_STATUSES} 之一")
