"""内容获客商城 Phase1 数据模型。"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


class ShopOnboardingApplication(Base):
    __tablename__ = "shop_onboarding_applications"
    __table_args__ = (
        UniqueConstraint("application_no", name="uq_shop_onboarding_applications_application_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_no: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    initiator: Mapped[str] = mapped_column(String(20), nullable=False, default="ops_assisted")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    contact_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    contact_mobile: Mapped[str] = mapped_column(String(11), nullable=False, default="")
    id_no: Mapped[str] = mapped_column(String(18), nullable=True)
    unified_social_credit_code: Mapped[str] = mapped_column(String(18), nullable=True)
    legal_rep_name: Mapped[str] = mapped_column(String(100), nullable=True)
    bank_account_info: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    qualification_files: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ocr_results: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reject_code: Mapped[str] = mapped_column(String(30), nullable=True)
    reject_reason: Mapped[str] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    remark: Mapped[str] = mapped_column(Text, nullable=True)
    merchant_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopOnboardingReviewLog(Base):
    """入驻审核日志。对照 04#ob-log · 06#p03-detail。"""

    __tablename__ = "shop_onboarding_review_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_onboarding_applications.id"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    operator_name: Mapped[str] = mapped_column(String(100), nullable=False, default="系统")
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShopMerchantAccount(Base):
    __tablename__ = "shop_merchant_accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_shop_merchant_accounts_tenant_id"),
        UniqueConstraint("merchant_no", name="uq_shop_merchant_accounts_merchant_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    merchant_no: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    onboarding_application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_onboarding_applications.id"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    contact_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    contact_mobile: Mapped[str] = mapped_column(String(11), nullable=False, default="")
    id_no: Mapped[str] = mapped_column(String(18), nullable=True)
    unified_social_credit_code: Mapped[str] = mapped_column(String(18), nullable=True)
    legal_rep_name: Mapped[str] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    onboarding_approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    fee_tier: Mapped[str] = mapped_column(String(20), nullable=True)
    current_subscription_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    account_manager_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    plan_label: Mapped[str] = mapped_column(String(100), nullable=True)
    plan_status: Mapped[str] = mapped_column(String(30), nullable=True, index=True)
    benefits_until: Mapped[date] = mapped_column(Date, nullable=True)
    store_count_active: Mapped[int] = mapped_column(nullable=False, default=0)
    store_quota: Mapped[int] = mapped_column(nullable=True)
    has_pending_renewal: Mapped[bool] = mapped_column(nullable=False, default=False)
    suspended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    close_reason_code: Mapped[str] = mapped_column(String(40), nullable=True)
    close_reason_text: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])
    account_manager: Mapped["User | None"] = relationship("User", foreign_keys=[account_manager_user_id])


class ShopTenantProspectAssignment(Base):
    """未入驻 tenant 预分配管家。对照 04#prospect。"""

    __tablename__ = "shop_tenant_prospect_assignments"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_shop_tenant_prospect_assignments_tenant"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    account_manager_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    assigned_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    remark: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopMerchantTag(Base):
    """平台商家标签字典。对照 04#mtag。"""

    __tablename__ = "shop_merchant_tags"
    __table_args__ = (UniqueConstraint("name", name="uq_shop_merchant_tags_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="blue")
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopMerchantTagLink(Base):
    """商家 ↔ 标签。"""

    __tablename__ = "shop_merchant_tag_links"
    __table_args__ = (UniqueConstraint("merchant_id", "tag_id", name="uq_shop_merchant_tag_links_pair"),)

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_merchant_accounts.id"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_merchant_tags.id"), primary_key=True)
    tagged_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShopMerchantServiceLog(Base):
    __tablename__ = "shop_merchant_service_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_merchant_accounts.id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="logged", index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    follow_up_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    operator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    related_onboarding_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    related_subscription_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    merchant: Mapped["ShopMerchantAccount"] = relationship("ShopMerchantAccount", foreign_keys=[merchant_id])
    operator: Mapped["User"] = relationship("User", foreign_keys=[operator_user_id])


class ShopAuditLog(Base):
    """P02-B 商家操作日志。对照 06#p02b-audit · 04 shop_audit_logs。"""

    __tablename__ = "shop_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_merchant_accounts.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    operator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    operator_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShopPlanFeature(Base):
    """功能字典（P10）：group 仅目录，leaf 可写入套餐 snapshot。"""

    __tablename__ = "shop_plan_features"
    __table_args__ = (UniqueConstraint("code", name="uq_shop_plan_features_code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    node_type: Mapped[str] = mapped_column(String(10), nullable=False)  # group | leaf
    parent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_plan_features.id"), nullable=True, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category: Mapped[str] = mapped_column(String(20), nullable=True)  # quota|usage|feature
    value_type: Mapped[str] = mapped_column(String(20), nullable=True)
    aggregate_mode: Mapped[str] = mapped_column(String(10), nullable=True)  # max|sum|any
    usage_period: Mapped[str] = mapped_column(String(20), nullable=True)
    meter_key: Mapped[str] = mapped_column(String(64), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopSubscriptionPlan(Base):
    """套餐模板（P10）。"""

    __tablename__ = "shop_subscription_plans"
    __table_args__ = (
        UniqueConstraint("code", name="uq_shop_subscription_plans_code"),
        UniqueConstraint("name", name="uq_shop_subscription_plans_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False, default="main")  # main|addon
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    replace_group: Mapped[str] = mapped_column(String(40), nullable=True)
    billing_period: Mapped[str] = mapped_column(String(20), nullable=False, default="yearly")
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    quotas: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    features: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    usage_limits: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    allowed_entity_types: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopMerchantSubscription(Base):
    """商家已购订阅（可多条 active）。"""

    __tablename__ = "shop_merchant_subscriptions"
    __table_args__ = (UniqueConstraint("subscription_no", name="uq_shop_merchant_subscriptions_no"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subscription_no: Mapped[str] = mapped_column(String(32), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_subscription_plans.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    purchase_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="stack")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    previous_subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_merchant_subscriptions.id"), nullable=True
    )
    plan_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    catalog_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    paid_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    remark: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    plan: Mapped["ShopSubscriptionPlan"] = relationship("ShopSubscriptionPlan", foreign_keys=[plan_id])


class ShopMerchantFeatureUsage(Base):
    """租户级用量计数（多套餐共享同一计数池）。"""

    __tablename__ = "shop_merchant_feature_usage"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "feature_code",
            "period_key",
            name="uq_shop_merchant_feature_usage_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    feature_code: Mapped[str] = mapped_column(String(64), nullable=False)
    period_key: Mapped[str] = mapped_column(String(20), nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopPlatformCategory(Base):
    """P04 平台类目与费率。"""

    __tablename__ = "shop_platform_categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID] = mapped_column(nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    code_source: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    platform_fee_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    settlement_rule: Mapped[str] = mapped_column(String(40), nullable=False, default="standard")
    require_qualifications: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="enabled", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    updated_by: Mapped[uuid.UUID] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopCategoryEnableApplication(Base):
    """P04-D 禁入类目启用审批。对照 #p04d。"""

    __tablename__ = "shop_category_enable_applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_platform_categories.id"), nullable=False, index=True
    )
    proposed_platform_fee_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    proposed_require_qualifications: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewer_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    reject_reason: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopPlatformNumberRule(Base):
    """平台业务编码规则（P08-F / P04-E）。无 tenant_id。"""

    __tablename__ = "shop_platform_number_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    suffix: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    date_format: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    seq_width: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    reset_period: Mapped[str] = mapped_column(String(10), nullable=False, default="once")
    inherit_parent_code: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    separator: Mapped[str] = mapped_column(String(4), nullable=False, default=".")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[uuid.UUID] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopPlatformNumberCounter(Base):
    """平台业务编码计数器。"""

    __tablename__ = "shop_platform_number_counters"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "scope_key", "period_key", name="uq_shop_platform_number_counters_scope"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    period_key: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopProduct(Base):
    __tablename__ = "shop_products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # course|digital|service
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(300), nullable=True)
    cover_url: Mapped[str] = mapped_column(String(500), nullable=True)
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(nullable=True, index=True)
    ref_type: Mapped[str] = mapped_column(String(30), nullable=True)
    ref_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    last_review_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    compliance_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    refund_policy: Mapped[str] = mapped_column(String(30), nullable=False, default="before_fulfill")
    sales_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class ShopProductReview(Base):
    __tablename__ = "shop_product_reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_products.id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    auto_result: Mapped[str] = mapped_column(String(20), nullable=False, default="pass")
    auto_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    manual_result: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    reject_reason: Mapped[str] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShopStore(Base):
    __tablename__ = "shop_stores"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_shop_stores_tenant_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_merchant_accounts.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    logo_url: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    wx_mp_app_id: Mapped[str] = mapped_column(String(64), nullable=True)
    default_category_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    allow_cross_shop_redeem: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopStoreSettings(Base):
    """A19 单店设置。对照 #a19 · 04 shop_store_settings。"""

    __tablename__ = "shop_store_settings"
    __table_args__ = (UniqueConstraint("shop_id", name="uq_shop_store_settings_shop_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False)
    intro: Mapped[str] = mapped_column(Text, nullable=True)
    service_phone: Mapped[str] = mapped_column(String(32), nullable=True)
    theme_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#1677ff")
    close_order_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    default_refund_policy: Mapped[str] = mapped_column(
        String(30), nullable=False, default="before_fulfill"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopPaymentOnboarding(Base):
    """A15 微信支付进件（商家级）。对照 #a15 · §8.7.3。"""

    __tablename__ = "shop_payment_onboardings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_shop_payment_onboardings_tenant"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_merchant_accounts.id"), nullable=True, index=True
    )
    onboarding_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_submitted", index=True
    )
    settlement_bank: Mapped[str] = mapped_column(String(100), nullable=True)
    settlement_account: Mapped[str] = mapped_column(String(64), nullable=True)
    settlement_account_name: Mapped[str] = mapped_column(String(200), nullable=True)
    remark: Mapped[str] = mapped_column(Text, nullable=True)
    wx_sub_mch_id: Mapped[str] = mapped_column(String(32), nullable=True)
    mch_name: Mapped[str] = mapped_column(String(200), nullable=True)
    reject_reason: Mapped[str] = mapped_column(Text, nullable=True)
    entity_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopSettlementBatch(Base):
    __tablename__ = "shop_settlement_batches"
    __table_args__ = (UniqueConstraint("batch_no", name="uq_shop_settlement_batches_batch_no"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(32), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    gross_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    platform_fee_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    refund_reversal_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    net_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    opening_balance_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    period_net_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    transfer_voucher_url: Mapped[str] = mapped_column(Text, nullable=True)
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    fail_reason: Mapped[str] = mapped_column(Text, nullable=True)
    confirm_remark: Mapped[str] = mapped_column(Text, nullable=True)
    offset_by_batch_id: Mapped[uuid.UUID] = mapped_column(nullable=True, index=True)
    offset_settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["ShopSettlementItem"]] = relationship(
        "ShopSettlementItem", back_populates="batch", cascade="all, delete-orphan"
    )
    operator: Mapped["User | None"] = relationship("User", foreign_keys=[operator_id])


class ShopSettlementItem(Base):
    __tablename__ = "shop_settlement_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_settlement_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[str] = mapped_column(String(24), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(nullable=True, index=True)
    refund_id: Mapped[uuid.UUID] = mapped_column(nullable=True, index=True)
    source_batch_id: Mapped[uuid.UUID] = mapped_column(nullable=True, index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    note: Mapped[str] = mapped_column(Text, nullable=True)

    batch: Mapped["ShopSettlementBatch"] = relationship("ShopSettlementBatch", back_populates="items")


class ShopBuyer(Base):
    """买家（tenant 内 mobile 归一；与 CRM Contact 隔离）。"""

    __tablename__ = "shop_buyers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "mobile", name="uq_shop_buyers_tenant_mobile"),
        UniqueConstraint("tenant_id", "wx_openid", name="uq_shop_buyers_tenant_openid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    mobile: Mapped[str] = mapped_column(String(11), nullable=True, index=True)
    wx_openid: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    nickname: Mapped[str] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopOrder(Base):
    """商城订单（独立模型，禁止复用 B2B Order）。状态见 04#enum-master。"""

    __tablename__ = "shop_orders"
    __table_args__ = (UniqueConstraint("order_no", name="uq_shop_orders_order_no"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_buyers.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_products.id"), nullable=False, index=True)
    product_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    order_no: Mapped[str] = mapped_column(String(32), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # course|digital|service
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_payment", index=True)
    paid_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    paid_channel: Mapped[str] = mapped_column(String(30), nullable=True)
    refund_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=True)
    refunded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    refund_reason: Mapped[str] = mapped_column(Text, nullable=True)
    claim_token: Mapped[str] = mapped_column(String(64), nullable=True)
    claim_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_buyer_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    needs_red_flush: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invoice_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="private")
    wx_transaction_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    buyer_mobile_snapshot: Mapped[str] = mapped_column(String(11), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopEntitlement(Base):
    """买家权益（与套餐 merge_entitlements 无关）。UK(order_id) 防双开。"""

    __tablename__ = "shop_entitlements"
    __table_args__ = (UniqueConstraint("order_id", name="uq_shop_entitlements_order_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_buyers.id"), nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_orders.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_products.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str] = mapped_column(Text, nullable=True)
    remaining_count: Mapped[int] = mapped_column(Integer, nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=True)
    verify_code: Mapped[str] = mapped_column(String(16), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopEnrollment(Base):
    """选课记录（独立表，不映射 CRM Contact）。"""

    __tablename__ = "shop_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_buyers.id"), nullable=False, index=True)
    entitlement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_entitlements.id"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    progress_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_learned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopRefund(Base):
    """退款单。状态：processing | succeeded | failed。"""

    __tablename__ = "shop_refunds"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_orders.id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing", index=True)
    initiated_by: Mapped[str] = mapped_column(String(20), nullable=False)  # buyer|merchant
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    entitlement_revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    wx_refund_id: Mapped[str] = mapped_column(String(64), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopPaymentConfig(Base):
    """商家微信支付配置（A15）。"""

    __tablename__ = "shop_payment_configs"
    __table_args__ = (UniqueConstraint("tenant_id", "shop_id", name="uq_shop_payment_configs_tenant_shop"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_merchant_accounts.id"), nullable=True, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    wx_mch_id: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    wx_app_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    wx_api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    wx_cert_sn: Mapped[str] = mapped_column(String(64), nullable=True)
    wx_cert_pem_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
    wx_notify_url: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    onboarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    onboarded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopPayment(Base):
    """支付单（与订单 1:1 主支付）。"""

    __tablename__ = "shop_payments"
    __table_args__ = (UniqueConstraint("order_id", name="uq_shop_payments_order_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_orders.id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    prepay_id: Mapped[str] = mapped_column(String(64), nullable=True)
    wx_transaction_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    fail_reason: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopPaymentLog(Base):
    """支付审计日志。"""

    __tablename__ = "shop_payment_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_orders.id"), nullable=True, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    wx_transaction_id: Mapped[str] = mapped_column(String(64), nullable=True)
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    error_msg: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShopColumn(Base):
    """A04 专栏。"""

    __tablename__ = "shop_columns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    intro: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class ShopLesson(Base):
    """A05 课时。"""

    __tablename__ = "shop_lessons"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    column_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_columns.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, default="video")
    media_id: Mapped[str] = mapped_column(String(64), nullable=True)
    media_url: Mapped[str] = mapped_column(String(500), nullable=True)
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_trial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trial_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class ShopDigitalPackage(Base):
    """A06 资料包。"""

    __tablename__ = "shop_digital_packages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    deliver_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="download")
    max_downloads: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class ShopDigitalAsset(Base):
    """A06 资料包文件。"""

    __tablename__ = "shop_digital_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    package_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_digital_packages.id"), nullable=False, index=True
    )
    file_id: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    mime: Mapped[str] = mapped_column(String(100), nullable=False, default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    previewable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShopServiceOffer(Base):
    """A07 服务定义（预约 / 次数卡）。"""

    __tablename__ = "shop_service_offers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="booking")  # booking|times_card
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    total_times: Mapped[int] = mapped_column(Integer, nullable=True)
    valid_days: Mapped[int] = mapped_column(Integer, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class ShopServiceSlot(Base):
    """A07 可预约时段。"""

    __tablename__ = "shop_service_slots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    service_offer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_service_offers.id"), nullable=False, index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    booked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopBooking(Base):
    """服务预约。"""

    __tablename__ = "shop_bookings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_buyers.id"), nullable=False, index=True)
    entitlement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_entitlements.id"), nullable=False, index=True
    )
    service_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_products.id"), nullable=False, index=True
    )
    slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_service_slots.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="booked", index=True)
    booked_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    booked_time_slot: Mapped[str] = mapped_column(String(32), nullable=False)
    cancelled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopVerification(Base):
    """核销记录。"""

    __tablename__ = "shop_verifications"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_shop_verifications_idem"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_buyers.id"), nullable=False, index=True)
    entitlement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_entitlements.id"), nullable=False, index=True
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_bookings.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False, default="times_card_deduct")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success", index=True)
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    verify_code: Mapped[str] = mapped_column(String(16), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=True)
    deducted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShopInvoiceRequest(Base):
    """发票申请。"""

    __tablename__ = "shop_invoice_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_buyers.id"), nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_orders.id"), nullable=False, index=True)
    invoice_type: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    title_type: Mapped[str] = mapped_column(String(20), nullable=False)  # person|company
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_no: Mapped[str] = mapped_column(String(32), nullable=True)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=True)
    bank_account: Mapped[str] = mapped_column(String(64), nullable=True)
    address: Mapped[str] = mapped_column(String(300), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    email: Mapped[str] = mapped_column(String(120), nullable=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted", index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    invoice_no: Mapped[str] = mapped_column(String(64), nullable=True)
    invoice_url: Mapped[str] = mapped_column(String(500), nullable=True)
    remark: Mapped[str] = mapped_column(Text, nullable=True)
    needs_red_flush: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reject_reason: Mapped[str] = mapped_column(Text, nullable=True)
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopExportTask(Base):
    """列表异步导出任务。对照 01#a13 导出（站内信本批不接，页内下载）。"""

    __tablename__ = "shop_export_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    resource: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    filters_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    file_name: Mapped[str] = mapped_column(String(200), nullable=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class ShopLessonProgress(Base):
    """学课进度（续播）。"""

    __tablename__ = "shop_lesson_progress"
    __table_args__ = (
        UniqueConstraint("entitlement_id", "lesson_id", name="uq_shop_lesson_progress_ent_lesson"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_buyers.id"), nullable=False, index=True)
    entitlement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_entitlements.id"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    position_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_learned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopDigitalDownload(Base):
    """资料下载计数（M09）。"""

    __tablename__ = "shop_digital_downloads"
    __table_args__ = (
        UniqueConstraint("entitlement_id", "file_id", name="uq_shop_digital_dl_ent_file"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_buyers.id"), nullable=False, index=True)
    entitlement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shop_entitlements.id"), nullable=False, index=True
    )
    file_id: Mapped[str] = mapped_column(String(64), nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopChannelSetting(Base):
    """公域对接配置（租户级）。"""

    __tablename__ = "shop_channel_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_shop_channel_settings_tenant"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    enabled_combos: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # e.g. ["1A"]
    deal_link: Mapped[str] = mapped_column(String(8), nullable=False, default="1")
    path_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="A")
    bind_scope: Mapped[str] = mapped_column(String(20), nullable=False, default="tenant")
    bind_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unbound")
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    webhook_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    webhook_tested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    douyin_shop_id: Mapped[str] = mapped_column(String(64), nullable=True)
    douyin_webhook_secret: Mapped[str] = mapped_column(String(128), nullable=True)
    douyin_configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopChannelMapping(Base):
    """公域商品映射。"""

    __tablename__ = "shop_channel_mappings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "channel",
            "channel_product_id",
            name="uq_shop_channel_mappings_ch_pid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_products.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # douyin|course_lib
    channel_product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_product_url: Mapped[str] = mapped_column(String(500), nullable=True)
    combo: Mapped[str] = mapped_column(String(8), nullable=True)  # 1A|1B|2A|2B，路径取末位
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="mapped", index=True)
    # A14 双轴：挂载状态 + 外部审核
    external_audit_status: Mapped[str] = mapped_column(String(20), nullable=True)
    mount_blocked_code: Mapped[str] = mapped_column(String(64), nullable=True)
    mount_blocked_reason: Mapped[str] = mapped_column(Text, nullable=True)
    blocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopChannelAuditLog(Base):
    """公域挂载审核日志。"""

    __tablename__ = "shop_channel_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=True, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_products.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShopWebhookEvent(Base):
    """Webhook 事件日志。"""

    __tablename__ = "shop_webhook_events"
    __table_args__ = (
        UniqueConstraint("channel", "event_id", name="uq_shop_webhook_events_ch_eid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_error: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShopClaimToken(Base):
    """领权令牌。"""

    __tablename__ = "shop_claim_tokens"
    __table_args__ = (UniqueConstraint("token", name="uq_shop_claim_tokens_token"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_orders.id"), nullable=False, index=True)
    buyer_mobile: Mapped[str] = mapped_column(String(11), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_buyers.id"), nullable=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShopSmsLog(Base):
    """商城短信发送记录。"""

    __tablename__ = "shop_sms_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=True, index=True)
    buyer_mobile: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")
    provider_msg_id: Mapped[str] = mapped_column(String(64), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlatformSmsSignature(Base):
    """平台短信签名（P12）。商家 A15-S 只读。"""

    __tablename__ = "platform_sms_signatures"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    provider_sig_id: Mapped[str] = mapped_column(String(64), nullable=True)
    remark: Mapped[str] = mapped_column(Text, nullable=True)
    reject_reason: Mapped[str] = mapped_column(Text, nullable=True)
    qualification_files: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PlatformSmsTemplate(Base):
    """平台短信模板（P12）。商家 A15-S 只读。"""

    __tablename__ = "platform_sms_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    template_code: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False, default="claim_link")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    is_default_claim: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content_preview: Mapped[str] = mapped_column(Text, nullable=True)
    signature_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_sms_signatures.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopTenantSettings(Base):
    """商家租户设置（A15-S 领权参数等）。对照 #a15-sms · 04 shop_tenant_settings。"""

    __tablename__ = "shop_tenant_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_shop_tenant_settings_tenant"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    sms_signature_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_sms_signatures.id"), nullable=True
    )
    claim_template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_sms_templates.id"), nullable=True
    )
    claim_landing_base: Mapped[str] = mapped_column(String(500), nullable=True)
    claim_expire_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    domain_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    domain_verified_base: Mapped[str] = mapped_column(String(500), nullable=True)
    disabled_shop_role_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopStoreMembership(Base):
    """店员单店范围。对照 #a16a · 04 shop_store_memberships。"""

    __tablename__ = "shop_store_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_shop_store_memberships_user_tenant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant_roles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShopModerationCase(Base):
    """P07 违规稽查工单。对照 04#moderate · 06#p07。"""

    __tablename__ = "shop_moderation_cases"
    __table_args__ = (UniqueConstraint("case_no", name="uq_shop_moderation_cases_case_no"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    case_no: Mapped[str] = mapped_column(String(32), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_stores.id"), nullable=False, index=True)
    case_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(30), nullable=False)
    object_ref: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_products.id"), nullable=True, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shop_orders.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_ref_id: Mapped[str] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    assignee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    force_off_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    off_reason_type: Mapped[str] = mapped_column(String(40), nullable=True)
    off_reason_text: Mapped[str] = mapped_column(Text, nullable=True)
    resolution: Mapped[str] = mapped_column(String(40), nullable=True)
    conclusion: Mapped[str] = mapped_column(Text, nullable=True)
    notify_in_app: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notify_sms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attachments_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    timeline_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PlatformChannelCredential(Base):
    """平台级渠道凭据。对照 04#platform_channel_credentials · 06#p06。"""

    __tablename__ = "platform_channel_credentials"
    __table_args__ = (UniqueConstraint("channel", name="uq_platform_channel_credentials_channel"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    secret_enc: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prev_secret_enc: Mapped[str] = mapped_column(Text, nullable=True)
    grace_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    public_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_tested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_ok: Mapped[bool] = mapped_column(Boolean, nullable=True)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShopPlatformPermissionAudit(Base):
    """P08-B：保存商城角色/权限写审计。对照 06#p08b。"""

    __tablename__ = "shop_platform_permission_audits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    target_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    operator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    role_from: Mapped[str] = mapped_column(String(50), nullable=True)
    role_to: Mapped[str] = mapped_column(String(50), nullable=True)
    permissions_from: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    permissions_to: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
