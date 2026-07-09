"""CRM Schema API Schemas。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FieldDefinitionOut(BaseModel):
    field_key: str
    label: str
    field_type: str
    is_system: bool
    is_required: bool
    is_unique: bool
    options: list
    default_value: str | None
    placeholder: str | None
    sort_order: int
    show_in_list_default: bool
    list_width: int | None
    is_active: bool
    storage: str
    list_locked: bool = False

    model_config = {"from_attributes": True}


class EntitySchemaOut(BaseModel):
    entity_type: str
    fields: list[FieldDefinitionOut]


class CustomFieldCreate(BaseModel):
    field_key: str = Field(min_length=3, max_length=80)
    label: str = Field(min_length=1, max_length=100)
    field_type: str
    is_required: bool = False
    options: list[str] = Field(default_factory=list)
    show_in_list_default: bool = False
    sort_order: int = 500
    placeholder: str | None = None


class FieldDefinitionUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    is_required: bool | None = None
    options: list[str] | None = None
    show_in_list_default: bool | None = None
    sort_order: int | None = None
    placeholder: str | None = None
    list_width: int | None = None


class ListColumnOut(BaseModel):
    field_key: str
    label: str
    field_type: str
    visible: bool = True
    width: int | None = None
    order: int = 0
    list_locked: bool = False


class ColumnPreferenceInput(BaseModel):
    field_key: str
    visible: bool = True
    width: int | None = None
    order: int = 0


class ViewPreferenceOut(BaseModel):
    entity_type: str
    view_kind: str = "list"
    columns: list[ListColumnOut]
    updated_at: datetime | None = None


class ViewPreferenceUpdate(BaseModel):
    columns: list[ColumnPreferenceInput]
