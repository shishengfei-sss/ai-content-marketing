"""CRM 业务表模型。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base

LEAD_STATUSES = ("待跟进", "跟进中", "有意向", "无意向", "已转化", "无效")
CUSTOMER_STATUSES = ("潜在", "意向", "成交", "在服", "暂停", "流失")
ACTIVITY_TYPES = ("call", "visit", "wechat", "email", "other")
TASK_STATUSES = ("open", "in_progress", "on_hold", "done", "cancelled")
TASK_PRIORITIES = ("low", "normal", "high")
CAMPAIGN_STATUSES = ("draft", "active", "ended")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    lead_number: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(100), nullable=True)
    mobile: Mapped[str] = mapped_column(String(20), nullable=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="待跟进")
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    territory_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    next_follow_up_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str] = mapped_column(Text, nullable=True)
    converted_customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    customer_number: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mobile: Mapped[str] = mapped_column(String(20), nullable=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="潜在")
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    territory_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    converted_from_lead_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("leads.id"), nullable=True)
    next_follow_up_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    contacts: Mapped[list["Contact"]] = relationship(back_populates="customer")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    mobile: Mapped[str] = mapped_column(String(20), nullable=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    wechat: Mapped[str] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(100), nullable=True)
    department: Mapped[str] = mapped_column(String(100), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_decision_maker: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remark: Mapped[str] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="contacts")


class CrmActivity(Base):
    __tablename__ = "crm_activities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("leads.id"), nullable=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=True, index=True)
    deal_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("deals.id"), nullable=True, index=True)
    activity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    entity_type: Mapped[str] = mapped_column(String(20), nullable=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SalesTerritory(Base):
    __tablename__ = "sales_territories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sales_territories.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=True)
    manager_membership_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenant_memberships.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MembershipSalesProfile(Base):
    __tablename__ = "membership_sales_profile"

    membership_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenant_memberships.id", ondelete="CASCADE"), primary_key=True
    )
    primary_territory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sales_territories.id"), nullable=True
    )
    reports_to_membership_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenant_memberships.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CrmTask(Base):
    __tablename__ = "crm_tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    task_number: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    planned_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    assignee_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    territory_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("leads.id"), nullable=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    content_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class MarketingCampaign(Base):
    __tablename__ = "marketing_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    campaign_number: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    goal: Mapped[str] = mapped_column(Text, nullable=True)
    channels: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    territory_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class CampaignContent(Base):
    __tablename__ = "campaign_contents"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contents.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


ENTITY_TYPES = (
    "lead",
    "customer",
    "contact",
    "task",
    "campaign",
    "deal",
    "quote",
    "contract",
    "order",
    "payment",
    "product",
)
PROTECTED_FIELD_KEYS = frozenset({"owner_user_id", "territory_id", "tenant_id"})
LIST_LOCKED_FIELD_KEYS: dict[str, frozenset[str]] = {
    "lead": frozenset({"company_name"}),
    "customer": frozenset({"company_name"}),
}


def is_list_locked_field(entity_type: str, field_key: str) -> bool:
    return field_key in LIST_LOCKED_FIELD_KEYS.get(entity_type, frozenset())


class EntityFieldDefinition(Base):
    __tablename__ = "entity_field_definitions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    field_key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    field_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    options: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    default_value: Mapped[str] = mapped_column(String(500), nullable=True)
    placeholder: Mapped[str] = mapped_column(String(200), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    show_in_list_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    list_width: Mapped[int] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validation: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    storage: Mapped[str] = mapped_column(String(10), nullable=False, default="seed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserEntityViewPreference(Base):
    __tablename__ = "user_entity_view_preferences"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    view_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="list")
    columns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EntityListView(Base):
    __tablename__ = "entity_list_views"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    sort: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    columns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    search_q: Mapped[str] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


IMPORT_JOB_STATUSES = ("draft", "previewing", "importing", "completed", "failed")
IMPORT_ROW_STATUSES = ("success", "skip", "error", "preview_ok", "preview_error")


class CrmImportJob(Base):
    __tablename__ = "crm_import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mapping: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    options: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    total_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(default=0, nullable=False)
    skip_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(default=0, nullable=False)
    columns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CrmImportRow(Base):
    __tablename__ = "crm_import_rows"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("crm_import_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index("ix_leads_tenant_owner", Lead.tenant_id, Lead.owner_user_id)
Index("ix_customers_tenant_owner", Customer.tenant_id, Customer.owner_user_id)
Index("ix_crm_tasks_tenant_assignee", CrmTask.tenant_id, CrmTask.assignee_user_id)


# ============================================================
# v0.7 CRM-2/3：商机与管道 + 报价/合同/订单/收款
# ============================================================

DEAL_STATUSES = ("open", "won", "lost", "abandoned")
DEAL_SOURCES = ("官网", "公众号", "小红书", "抖音", "线下", "转介绍", "电话", "导入", "营销活动", "其他")
QUOTE_STATUSES = ("draft", "sent", "accepted", "rejected", "expired", "ordered")
CONTRACT_STATUSES = ("draft", "sent", "signed", "executing", "expired", "terminated")
CONTRACT_TYPES = ("new", "renewal", "addon")
ORDER_STATUSES = ("draft", "confirmed", "executing", "completed", "cancelled")
ORDER_SOURCES = ("deal", "quote", "contract")
PAYMENT_STATUSES = ("pending", "confirmed", "reversed")
PAYMENT_METHODS = ("bank", "wechat", "alipay", "cash", "other")


class SalesPipeline(Base):
    __tablename__ = "sales_pipelines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SalesPipelineStage(Base):
    __tablename__ = "sales_pipeline_stages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sales_pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    probability: Mapped[int] = mapped_column(default=0, nullable=False)
    is_won_stage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_lost_stage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_closed_stage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=True)
    max_stay_days: Mapped[int] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    deal_number: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sales_pipelines.id"), nullable=False, index=True
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sales_pipeline_stages.id"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    expected_close_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    probability: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    loss_reason: Mapped[str] = mapped_column(String(200), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    next_step: Mapped[str] = mapped_column(String(200), nullable=True)
    deal_type: Mapped[str] = mapped_column(String(20), nullable=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    competitor: Mapped[str] = mapped_column(String(200), nullable=True)
    contact_role: Mapped[str] = mapped_column(String(50), nullable=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    territory_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    converted_from_lead_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    converted_order_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    lines: Mapped[list["DealLineItem"]] = relationship(
        cascade="all, delete-orphan",
        order_by="DealLineItem.sort_order",
        lazy="selectin",
    )


class DealLineItem(Base):
    __tablename__ = "deal_line_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    unit: Mapped[str] = mapped_column(String(30), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)


class DealTeamMember(Base):
    __tablename__ = "deal_team_members"
    __table_args__ = (UniqueConstraint("tenant_id", "deal_id", "user_id", name="uq_deal_team_member"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DealStageLog(Base):
    __tablename__ = "deal_stage_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_stage_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    to_stage_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str] = mapped_column(Text, nullable=True)


class DealCloseAnalysis(Base):
    __tablename__ = "deal_close_analyses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    close_type: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=True)
    competitor: Mapped[str] = mapped_column(String(200), nullable=True)
    detail: Mapped[str] = mapped_column(Text, nullable=True)
    improvement: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=True)
    list_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    cost_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    quote_number: Mapped[str] = mapped_column(String(50), nullable=False)
    deal_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("deals.id"), nullable=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    discount_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    converted_order_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["QuoteLine"]] = relationship(
        cascade="all, delete-orphan",
        order_by="QuoteLine.sort_order",
        lazy="selectin",
    )


class QuoteLine(Base):
    __tablename__ = "quote_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    quote_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    remark: Mapped[str] = mapped_column(Text, nullable=True)


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    contract_number: Mapped[str] = mapped_column(String(50), nullable=False)
    deal_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("deals.id"), nullable=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=False, index=True)
    quote_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    signed_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    file_url: Mapped[str] = mapped_column(String(500), nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    order_number: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), nullable=False, index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    deal_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("deals.id"), nullable=True, index=True)
    quote_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    contract_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    territory_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["OrderLine"]] = relationship(
        cascade="all, delete-orphan",
        order_by="OrderLine.sort_order",
        lazy="selectin",
    )


class OrderLine(Base):
    __tablename__ = "order_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    remark: Mapped[str] = mapped_column(Text, nullable=True)


class PaymentPlan(Base):
    __tablename__ = "payment_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    installment_no: Mapped[int] = mapped_column(nullable=False)
    plan_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    plan_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    remark: Mapped[str] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payment_number: Mapped[str] = mapped_column(String(50), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("payment_plans.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="bank")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    remark: Mapped[str] = mapped_column(String(500), nullable=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


Index("ix_deals_tenant_stage", Deal.tenant_id, Deal.stage_id)
Index("ix_deals_tenant_owner", Deal.tenant_id, Deal.owner_user_id)
Index("ix_orders_tenant_owner", Order.tenant_id, Order.owner_user_id)
Index("ix_payments_tenant_order", Payment.tenant_id, Payment.order_id)
Index("ix_products_tenant_code", Product.tenant_id, Product.code)

UniqueConstraint(Lead.tenant_id, Lead.lead_number, name="uq_leads_tenant_number")
UniqueConstraint(Customer.tenant_id, Customer.customer_number, name="uq_customers_tenant_number")
UniqueConstraint(CrmTask.tenant_id, CrmTask.task_number, name="uq_tasks_tenant_number")
UniqueConstraint(MarketingCampaign.tenant_id, MarketingCampaign.campaign_number, name="uq_campaigns_tenant_number")
UniqueConstraint(Deal.tenant_id, Deal.deal_number, name="uq_deals_tenant_number")
UniqueConstraint(Quote.tenant_id, Quote.quote_number, name="uq_quotes_tenant_number")
UniqueConstraint(Contract.tenant_id, Contract.contract_number, name="uq_contracts_tenant_number")
UniqueConstraint(Order.tenant_id, Order.order_number, name="uq_orders_tenant_number")
UniqueConstraint(Payment.tenant_id, Payment.payment_number, name="uq_payments_tenant_number")


class EntityNumberRule(Base):
    """租户级自动编号规则（按实体类型）。"""

    __tablename__ = "entity_number_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    prefix: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    date_format: Mapped[str] = mapped_column(String(20), nullable=False, default="%Y%m%d")
    seq_width: Mapped[int] = mapped_column(default=3, nullable=False)
    reset_period: Mapped[str] = mapped_column(String(10), nullable=False, default="daily")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("tenant_id", "entity_type", name="uq_number_rules_tenant_entity"),)


class EntityNumberCounter(Base):
    """自动编号原子计数器（按租户/实体/周期）。"""

    __tablename__ = "entity_number_counters"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    period_key: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    seq: Mapped[int] = mapped_column(default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_type", "period_key", name="uq_number_counters_tenant_entity_period"),
    )
