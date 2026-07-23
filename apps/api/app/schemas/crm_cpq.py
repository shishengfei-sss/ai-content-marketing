"""CPQ schemas (v1.3 W1–2)。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ProductParamCreate(BaseModel):
    param_name: str = Field(min_length=1, max_length=100)
    param_type: Literal["select", "number", "text"] = "select"
    options: list[Any] | None = None
    sort_order: int = 0
    is_active: bool = True


class ProductParamUpdate(BaseModel):
    param_name: str | None = Field(default=None, min_length=1, max_length=100)
    param_type: Literal["select", "number", "text"] | None = None
    options: list[Any] | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class ParamPricingCreate(BaseModel):
    option_value: str = Field(min_length=1, max_length=100)
    price_adjustment_type: Literal["fixed", "percentage", "multiplier"] = "fixed"
    price_adjustment_value: float


class ParamPricingUpdate(BaseModel):
    option_value: str | None = Field(default=None, min_length=1, max_length=100)
    price_adjustment_type: Literal["fixed", "percentage", "multiplier"] | None = None
    price_adjustment_value: float | None = None


class ParamPricingOut(BaseModel):
    id: UUID
    param_id: UUID
    option_value: str
    price_adjustment_type: str
    price_adjustment_value: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductParamOut(BaseModel):
    id: UUID
    tenant_id: UUID
    product_id: UUID
    param_name: str
    param_type: str
    options: list[Any] | None
    sort_order: int
    is_active: bool
    created_at: datetime
    pricings: list[ParamPricingOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ResolvePriceRequest(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: float = Field(default=1, gt=0)
    customer_level: str | None = None
    price_book_id: UUID | None = None


class ResolvePriceOut(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    unit_price: float
    source: Literal["price_book", "variant_list_price", "product_list_price"]
    price_book_id: UUID | None = None
    price_book_entry_id: UUID | None = None
    min_quantity: int | None = None


class CpqCalculateRequest(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: float = Field(default=1, gt=0)
    customer_level: str | None = None
    price_book_id: UUID | None = None
    selected_params: dict[str, Any] = Field(default_factory=dict)
    discount_rate: float = Field(default=0, ge=0, le=100)
    shipping_cost: float = Field(default=0, ge=0)
    min_margin_pct: float | None = Field(default=None, ge=0, le=100)
    confirm_low_margin: bool = False


class CpqCalculateOut(BaseModel):
    product_id: UUID
    base_unit_price: float
    adjusted_unit_price: float
    quantity: float
    subtotal: float
    discount_rate: float
    discount_amount: float
    shipping_cost: float
    final_price: float
    cost_estimate: float | None
    profit_margin_pct: float | None
    margin_warning: bool = False
    price_source: str
    price_book_id: UUID | None = None
    param_adjustments: list[dict[str, Any]] = Field(default_factory=list)


class CpqSaveQuoteRequest(BaseModel):
    """服务端重算后写入现有 quotes + quote_lines（FR-CPQ-07）。"""

    customer_id: UUID
    subject: str = Field(min_length=1, max_length=200)
    product_id: UUID
    deal_id: UUID | None = None
    scored_tender_lead_id: UUID | None = None
    contact_id: UUID | None = None
    variant_id: UUID | None = None
    quantity: float = Field(default=1, gt=0)
    customer_level: str | None = None
    price_book_id: UUID | None = None
    selected_params: dict[str, Any] = Field(default_factory=dict)
    discount_rate: float = Field(default=0, ge=0, le=100)
    shipping_cost: float = Field(default=0, ge=0)
    min_margin_pct: float | None = Field(default=None, ge=0, le=100)
    confirm_low_margin: bool = False
    valid_until: datetime | None = None


class CpqAiParseRequest(BaseModel):
    product_id: UUID
    text: str = Field(min_length=2, max_length=8000)


class CpqAiRecommendation(BaseModel):
    param_name: str
    suggested_value: str
    confidence: float = 0.6
    reason: str = ""


class CpqAiParseOut(BaseModel):
    product_id: UUID
    recommendations: list[CpqAiRecommendation] = Field(default_factory=list)
    quantity: float | None = None
    source: Literal["heuristic", "llm", "fake"] = "heuristic"
    requires_review: bool = True
    notes: str | None = None


class QuotePdfOut(BaseModel):
    id: UUID
    tenant_id: UUID
    quote_id: UUID
    file_path: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    status: Literal["generating", "completed", "failed"]
    error_message: str | None = None
    download_url: str | None = None
    generated_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
