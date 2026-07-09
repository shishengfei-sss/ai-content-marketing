"""CRM 导入 API Schemas。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ImportOptions(BaseModel):
    duplicate_key: str | None = "mobile"
    on_duplicate: str = "skip"
    default_owner_user_id: UUID | None = None
    default_territory_id: UUID | None = None
    default_status: str | None = None
    default_source: str | None = "导入"


class ImportJobPatch(BaseModel):
    mapping: dict[str, str] = Field(default_factory=dict)
    options: ImportOptions | None = None


class ImportPreviewRow(BaseModel):
    row_number: int
    status: str
    error_message: str | None = None
    data: dict = Field(default_factory=dict)


class ImportPreviewOut(BaseModel):
    job_id: UUID
    preview_rows: list[ImportPreviewRow]
    error_count: int
    ok_count: int


class ImportJobOut(BaseModel):
    id: UUID
    entity_type: str
    status: str
    file_name: str
    mapping: dict
    options: dict
    columns: list
    total_rows: int
    success_count: int
    skip_count: int
    error_count: int
    created_by_user_id: UUID
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportJobCreateOut(BaseModel):
    job_id: UUID
    columns: list[str]
    suggested_mapping: dict[str, str]


class ImportJobListResponse(BaseModel):
    items: list[ImportJobOut]
    total: int
    page: int
    page_size: int
