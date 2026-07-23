"""平台招标线索 L1 schemas。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


TENDER_STATUSES = ("draft", "published", "unpublished")
TENDER_CHANNELS = ("manual", "excel", "attachment_ai")


def _strip_opt_str(v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip()
    return s or None


class _TenderLeadFields(BaseModel):
    """手工/Excel/人审共用可选业务字段。"""

    industry: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    product_name: str | None = Field(default=None, max_length=200)
    quantity: str | None = Field(default=None, max_length=50)
    budget_min: float | None = None
    budget_max: float | None = None
    deadline: date | None = None
    contact_name: str | None = Field(default=None, max_length=100)
    contact_phone: str | None = Field(default=None, max_length=50)
    source_url: str | None = None
    summary: str | None = None
    project_no: str | None = Field(default=None, max_length=100)
    published_at: date | None = None
    procurement_method: str | None = Field(default=None, max_length=50)
    agent_name: str | None = Field(default=None, max_length=200)
    buyer_address: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    bid_open_date: date | None = None
    sme_preference: bool | None = None
    qualification_summary: str | None = None
    max_price_limit: float | None = None

    @field_validator("source_url", "project_no", "procurement_method", "agent_name", "buyer_address", "category")
    @classmethod
    def _strip_fields(cls, v: str | None) -> str | None:
        return _strip_opt_str(v)


class PlatformTenderLeadCreate(_TenderLeadFields):
    buyer_name: str = Field(min_length=1, max_length=200)
    source_channel: Literal["manual", "excel", "attachment_ai"] = "manual"
    status: Literal["draft", "published", "unpublished"] = "draft"
    has_source_document: bool = False


class PlatformTenderLeadUpdate(_TenderLeadFields):
    buyer_name: str | None = Field(default=None, min_length=1, max_length=200)
    source_channel: Literal["manual", "excel", "attachment_ai"] | None = None
    status: Literal["draft", "published", "unpublished"] | None = None
    has_source_document: bool | None = None


class PlatformTenderLeadOut(BaseModel):
    id: UUID
    buyer_name: str
    industry: str | None
    region: str | None
    product_name: str | None
    quantity: str | None
    budget_min: float | None
    budget_max: float | None
    deadline: date | None
    contact_name: str | None
    contact_phone: str | None
    source_url: str | None
    summary: str | None
    project_no: str | None = None
    published_at: date | None = None
    procurement_method: str | None = None
    agent_name: str | None = None
    buyer_address: str | None = None
    category: str | None = None
    bid_open_date: date | None = None
    sme_preference: bool | None = None
    qualification_summary: str | None = None
    max_price_limit: float | None = None
    source_channel: str
    status: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlatformTenderLeadListResponse(BaseModel):
    items: list[PlatformTenderLeadOut]
    total: int
    page: int
    page_size: int


class PlatformTenderExcelPreviewRow(BaseModel):
    row_num: int
    data: dict
    errors: list[str] = Field(default_factory=list)


class PlatformTenderExcelPreviewOut(BaseModel):
    rows: list[PlatformTenderExcelPreviewRow]
    valid_count: int
    error_count: int


class PlatformTenderExcelConfirmOut(BaseModel):
    created: int
    skipped: int
    ids: list[UUID] = Field(default_factory=list)


class TenderAttachmentOut(BaseModel):
    id: UUID
    platform_tender_lead_id: UUID | None
    file_name: str
    file_size: int
    mime_type: str | None
    uploaded_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ParseJobOut(BaseModel):
    id: UUID
    attachment_id: UUID
    status: str
    result_json: dict | None = None
    error_message: str | None = None
    confirmed_lead_id: UUID | None = None
    created_by: UUID
    created_at: datetime
    completed_at: datetime | None = None
    attachment: TenderAttachmentOut | None = None

    model_config = {"from_attributes": True}


class ParseTextRequest(BaseModel):
    """粘贴招投标正文，落盘为 txt 附件后走同一 parse_jobs 人审链路。"""

    text: str = Field(min_length=1, max_length=100_000)

    @field_validator("text")
    @classmethod
    def _strip_text(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("正文不能为空")
        return s


class ParseJobConfirmRequest(_TenderLeadFields):
    """人审确认字段；始终以 draft 写入 L1，须另走 publish（D7）。"""

    buyer_name: str = Field(min_length=1, max_length=200)
    has_source_document: bool = False


class ParseJobConfirmOut(BaseModel):
    parse_job_id: UUID
    lead: PlatformTenderLeadOut
    attachment_id: UUID
