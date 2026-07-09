"""CRM 列表视图 Schemas。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.crm_schema import ColumnPreferenceInput, ListColumnOut


class FilterCondition(BaseModel):
    field_key: str
    op: str
    value: object | None = None


class ViewFilters(BaseModel):
    logic: str = "and"
    conditions: list[FilterCondition] = Field(default_factory=list)


class ViewSortItem(BaseModel):
    field_key: str
    dir: str = "desc"


class ListViewCreate(BaseModel):
    entity_type: str
    name: str = Field(min_length=1, max_length=100)
    is_public: bool = False
    is_pinned: bool = False
    is_default: bool = False
    filters: ViewFilters = Field(default_factory=ViewFilters)
    sort: list[ViewSortItem] = Field(default_factory=list)
    columns: list[ColumnPreferenceInput] = Field(default_factory=list)
    search_q: str | None = None


class ListViewUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_public: bool | None = None
    is_pinned: bool | None = None
    is_default: bool | None = None
    filters: ViewFilters | None = None
    sort: list[ViewSortItem] | None = None
    columns: list[ColumnPreferenceInput] | None = None
    search_q: str | None = None


class ListViewOut(BaseModel):
    id: UUID
    entity_type: str
    name: str
    owner_user_id: UUID
    is_public: bool
    is_pinned: bool
    is_default: bool
    filters: dict
    sort: list
    columns: list
    search_q: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
