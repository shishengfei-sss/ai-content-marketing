"""ICP + 租户招标线索 L2 schemas。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class IcpConfigUpsert(BaseModel):
    target_industries: list[str] = Field(default_factory=list)
    target_regions: list[str] = Field(default_factory=list)
    company_size_min: int | None = None
    company_size_max: int | None = None
    min_budget_threshold: float | None = None
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    weight_industry: int = Field(default=30, ge=0, le=100)
    weight_company_size: int = Field(default=20, ge=0, le=100)
    weight_region: int = Field(default=15, ge=0, le=100)
    weight_budget: int = Field(default=20, ge=0, le=100)
    weight_urgency: int = Field(default=15, ge=0, le=100)
    is_active: bool = True

    @model_validator(mode="after")
    def _weights_sum_100(self) -> IcpConfigUpsert:
        total = (
            self.weight_industry
            + self.weight_company_size
            + self.weight_region
            + self.weight_budget
            + self.weight_urgency
        )
        if total != 100:
            raise ValueError(f"ICP 五维权重之和必须为 100，当前为 {total}")
        return self


class IcpConfigOut(BaseModel):
    id: UUID
    tenant_id: UUID
    target_industries: list[Any]
    target_regions: list[Any]
    company_size_min: int | None
    company_size_max: int | None
    min_budget_threshold: float | None
    include_keywords: list[Any]
    exclude_keywords: list[Any]
    weight_industry: int
    weight_company_size: int
    weight_region: int
    weight_budget: int
    weight_urgency: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScoredTenderLeadOut(BaseModel):
    id: UUID
    platform_tender_lead_id: UUID
    tenant_id: UUID
    match_score: int
    score_breakdown: dict
    status: str
    converted_lead_id: UUID | None
    assigned_to: UUID | None
    created_at: datetime
    updated_at: datetime
    # 只读展开 L1 字段
    buyer_name: str | None = None
    industry: str | None = None
    region: str | None = None
    product_name: str | None = None
    quantity: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    deadline: date | None = None
    source_url: str | None = None
    summary: str | None = None
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

    model_config = {"from_attributes": True}


class ScoredTenderLeadListResponse(BaseModel):
    items: list[ScoredTenderLeadOut]
    total: int
    page: int
    page_size: int


class TenderClaimOut(BaseModel):
    scored_tender_lead_id: UUID
    lead_id: UUID
    deal_created: bool = False


class TenderAnalyticsOut(BaseModel):
    """招标线索效果看板（FR-TENDER-09）。"""

    total_pushed: int = 0
    claimed_count: int = 0
    follow_rate: float = 0.0  # 已处理（非 pending）/ 总推送
    converted_to_deal_count: int = 0
    conversion_rate: float = 0.0  # 转 Deal 数 / 总推送
    high_match_count: int = 0
    high_match_rate: float = 0.0  # match_score>=60 / 总推送
    invalid_expired_count: int = 0
    invalid_expired_rate: float = 0.0
    score_buckets: list[dict[str, Any]] = Field(default_factory=list)
    weekly_trend: list[dict[str, Any]] = Field(default_factory=list)
