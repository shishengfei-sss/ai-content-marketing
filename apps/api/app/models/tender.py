"""招标线索相关模型（平台公共池 L1、ICP、租户匹配池 L2）。"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database import Base


class PlatformTenderLead(Base):
    """平台公共招标线索池 L1（无 tenant_id）。"""

    __tablename__ = "platform_tender_leads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    buyer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=True)
    region: Mapped[str] = mapped_column(String(100), nullable=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=True)
    quantity: Mapped[str] = mapped_column(String(50), nullable=True)
    budget_min: Mapped[float] = mapped_column(Numeric(15, 2), nullable=True)
    budget_max: Mapped[float] = mapped_column(Numeric(15, 2), nullable=True)
    deadline: Mapped[date] = mapped_column(Date, nullable=True)
    contact_name: Mapped[str] = mapped_column(String(100), nullable=True)
    contact_phone: Mapped[str] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    # 销售跟进增强字段（v1.3.1）
    project_no: Mapped[str] = mapped_column(String(100), nullable=True)
    published_at: Mapped[date] = mapped_column(Date, nullable=True)
    procurement_method: Mapped[str] = mapped_column(String(50), nullable=True)
    agent_name: Mapped[str] = mapped_column(String(200), nullable=True)
    buyer_address: Mapped[str] = mapped_column(String(200), nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    bid_open_date: Mapped[date] = mapped_column(Date, nullable=True)
    sme_preference: Mapped[bool] = mapped_column(Boolean, nullable=True)
    qualification_summary: Mapped[str] = mapped_column(Text, nullable=True)
    max_price_limit: Mapped[float] = mapped_column(Numeric(15, 2), nullable=True)
    source_channel: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TenderAttachment(Base):
    """平台公共池招标附件（确认前可不挂 L1）。"""

    __tablename__ = "tender_attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    platform_tender_lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("platform_tender_leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ParseJob(Base):
    """附件 AI 解析任务：succeeded 后人审 confirm 才写 L1。"""

    __tablename__ = "parse_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tender_attachments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    confirmed_lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("platform_tender_leads.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class IcpConfig(Base):
    """租户 ICP 画像（权重和必须 100）。"""

    __tablename__ = "icp_configs"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_icp_configs_tenant_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    target_industries: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    target_regions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    company_size_min: Mapped[int] = mapped_column(Integer, nullable=True)
    company_size_max: Mapped[int] = mapped_column(Integer, nullable=True)
    min_budget_threshold: Mapped[float] = mapped_column(Numeric(15, 2), nullable=True)
    include_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    exclude_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    weight_industry: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    weight_company_size: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    weight_region: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    weight_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    weight_urgency: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ScoredTenderLead(Base):
    """租户匹配池 L2。"""

    __tablename__ = "scored_tender_leads"
    __table_args__ = (
        UniqueConstraint("platform_tender_lead_id", "tenant_id", name="uq_scored_tender_tenant_platform"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    platform_tender_lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("platform_tender_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, index=True)
    match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    converted_lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
