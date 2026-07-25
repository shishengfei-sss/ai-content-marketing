"""线索 CRUD。"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import uuid_eq
from app.dependencies import TenantContext
from app.models.crm import CRM_SOURCE_OPTIONS, Contact, CrmActivity, Customer, Lead
from app.schemas.crm import LeadCreate, LeadUpdate, validate_lead_mobile_value, validate_lead_status
from app.services.crm.crm_scope_service import (
    assert_can_mutate_lead,
    assert_can_view_lead,
    can_view_customer,
)
from app.services.crm.number_service import generate_number
from app.services.crm.sales_org_service import (
    apply_creator_org_defaults,
    apply_owner_org_snapshot,
    assert_can_assign_owner,
    get_territory,
)
from app.services.crm.schema_service import validate_extra_data
from app.services.crm.utm_service import merge_utm_into_lead_fields


def _normalize_crm_source(value: str | None) -> str | None:
    """空串/非法来源归一为 None，避免转化建商机时 DealCreate 校验抛 500。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text not in CRM_SOURCE_OPTIONS:
        return None
    return text


def _perm_set(ctx: TenantContext) -> set[str]:
    return {p.permission_code for p in ctx.membership.role.permissions}


def get_lead(db: Session, tenant_id: UUID, lead_id: UUID) -> Lead | None:
    return (
        db.query(Lead)
        .filter(
            uuid_eq(Lead.id, lead_id),
            Lead.tenant_id == tenant_id,
            Lead.deleted_at.is_(None),
        )
        .first()
    )


def heal_converted_lead_status(db: Session, lead: Lead) -> Lead:
    """已关联客户但状态被跟进改乱时，纠正为「已转化」。"""
    if lead.converted_customer_id and lead.status != "已转化":
        lead.status = "已转化"
        db.commit()
        db.refresh(lead)
    return lead


def create_lead(db: Session, ctx: TenantContext, data: LeadCreate) -> Lead:
    from app.services.text_sanitize import sanitize_plain_text

    validate_lead_status(data.status)
    mobile, mobile_err = validate_lead_mobile_value(data.mobile, required=True)
    if mobile_err:
        raise HTTPException(status_code=422, detail=mobile_err)
    company_name = sanitize_plain_text(data.company_name) or ""
    if not company_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="公司名称不能为空")
    extra = validate_extra_data(db, ctx.tenant_id, "lead", data.extra_data, is_create=True)
    if getattr(data, "industry", None):
        extra = dict(extra or {})
        extra.setdefault("industry", str(data.industry).strip())
    if data.territory_id is not None and not get_territory(db, ctx.tenant_id, data.territory_id):
        raise HTTPException(status_code=404, detail="地区不存在")
    territory_id, manager_user_id = apply_creator_org_defaults(db, ctx, territory_id=data.territory_id)
    if territory_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="销售区域不能为空：请选择销售区域，或在「设置 → 销售组织」中配置本人主地区",
        )
    utm = merge_utm_into_lead_fields(
        source=data.source,
        source_detail=data.source_detail,
        utm_source=data.utm_source,
        utm_medium=data.utm_medium,
        utm_campaign=data.utm_campaign,
        landing_url=data.landing_url,
    )
    lead = Lead(
        tenant_id=ctx.tenant_id,
        lead_number=generate_number(db, ctx.tenant_id, "lead"),
        company_name=company_name,
        contact_name=data.contact_name,
        mobile=mobile,
        phone=data.phone,
        email=data.email,
        source=utm.get("source"),
        source_detail=utm.get("source_detail"),
        utm_source=utm.get("utm_source"),
        utm_medium=utm.get("utm_medium"),
        utm_campaign=utm.get("utm_campaign"),
        landing_url=utm.get("landing_url"),
        acquisition_cost=Decimal(str(data.acquisition_cost)) if data.acquisition_cost is not None else None,
        title=data.title,
        lead_score=data.lead_score,
        department=data.department,
        country=data.country or "中国",
        status=data.status,
        owner_user_id=ctx.user.id,
        territory_id=territory_id,
        manager_user_id=manager_user_id,
        remark=data.remark,
        extra_data=extra,
        campaign_id=data.campaign_id,
        created_by_user_id=ctx.user.id,
    )
    db.add(lead)
    db.flush()
    from app.services.crm.assignment_service import apply_assignment_rules

    apply_assignment_rules(db, ctx, lead)
    db.commit()
    db.refresh(lead)
    return lead


def update_lead(db: Session, ctx: TenantContext, lead: Lead, data: LeadUpdate) -> Lead:
    perms = _perm_set(ctx)
    changing_owner = data.owner_user_id is not None and data.owner_user_id != lead.owner_user_id
    # 除分配负责人外，其它字段变更仅负责人可操作
    mutate_keys = set(data.model_fields_set) - {"owner_user_id"}
    if mutate_keys:
        assert_can_mutate_lead(ctx, lead)

    if changing_owner:
        if "crm.lead.assign" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限分配负责人")
        assert_can_assign_owner(db, ctx, data.owner_user_id)
        lead.owner_user_id = data.owner_user_id
        # 跟随新负责人落地区/汇报上级，避免原负责人因地区/上级快照仍可见
        snap_territory, snap_manager = apply_owner_org_snapshot(db, ctx.tenant_id, data.owner_user_id)
        if data.territory_id is None:
            lead.territory_id = snap_territory
        lead.manager_user_id = snap_manager
        if getattr(lead, "pool_id", None) is not None:
            lead.pool_id = None
            lead.claimed_at = None
    if data.company_name is not None:
        lead.company_name = data.company_name.strip()
    if data.contact_name is not None:
        lead.contact_name = data.contact_name
    if data.mobile is not None:
        mobile, mobile_err = validate_lead_mobile_value(data.mobile, required=True)
        if mobile_err:
            raise HTTPException(status_code=422, detail=mobile_err)
        lead.mobile = mobile
    if data.phone is not None:
        lead.phone = data.phone
    if data.email is not None:
        lead.email = data.email
    if data.source is not None:
        lead.source = data.source
    if data.source_detail is not None:
        lead.source_detail = data.source_detail
    if data.utm_source is not None:
        lead.utm_source = data.utm_source
    if data.utm_medium is not None:
        lead.utm_medium = data.utm_medium
    if data.utm_campaign is not None:
        lead.utm_campaign = data.utm_campaign
    if data.landing_url is not None:
        parsed = merge_utm_into_lead_fields(
            source=lead.source,
            source_detail=lead.source_detail,
            utm_source=lead.utm_source,
            utm_medium=lead.utm_medium,
            utm_campaign=lead.utm_campaign,
            landing_url=data.landing_url,
        )
        lead.landing_url = parsed.get("landing_url")
        if not lead.utm_source and parsed.get("utm_source"):
            lead.utm_source = parsed.get("utm_source")
        if not lead.utm_medium and parsed.get("utm_medium"):
            lead.utm_medium = parsed.get("utm_medium")
        if not lead.utm_campaign and parsed.get("utm_campaign"):
            lead.utm_campaign = parsed.get("utm_campaign")
        if not lead.source_detail and parsed.get("source_detail"):
            lead.source_detail = parsed.get("source_detail")
    if data.acquisition_cost is not None:
        lead.acquisition_cost = Decimal(str(data.acquisition_cost))
    if data.title is not None:
        lead.title = data.title
    if data.lead_score is not None:
        lead.lead_score = data.lead_score
    if data.department is not None:
        lead.department = data.department
    if data.country is not None:
        lead.country = data.country
    if data.status is not None:
        validate_lead_status(data.status)
        if (lead.converted_customer_id or lead.status == "已转化") and data.status != "已转化":
            raise HTTPException(status_code=409, detail="线索已转化，不可改回其他状态")
        lead.status = data.status
    if data.remark is not None:
        lead.remark = data.remark
    if data.extra_data is not None:
        merged = dict(lead.extra_data or {})
        merged.update(data.extra_data)
        lead.extra_data = validate_extra_data(db, ctx.tenant_id, "lead", merged)
    if "campaign_id" in data.model_fields_set:
        lead.campaign_id = data.campaign_id
    if data.territory_id is not None:
        if not get_territory(db, ctx.tenant_id, data.territory_id):
            raise HTTPException(status_code=404, detail="地区不存在")
        lead.territory_id = data.territory_id
    db.commit()
    db.refresh(lead)
    return lead


def soft_delete_lead(db: Session, ctx: TenantContext, lead: Lead) -> None:
    assert_can_mutate_lead(ctx, lead)
    lead.deleted_at = datetime.now(timezone.utc)
    db.commit()


def require_lead(db: Session, ctx: TenantContext, lead_id: UUID) -> Lead:
    lead = get_lead(db, ctx.tenant_id, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    assert_can_view_lead(
        ctx,
        db,
        lead.owner_user_id,
        lead.territory_id,
        created_by_user_id=lead.created_by_user_id,
        manager_user_id=getattr(lead, "manager_user_id", None),
        pool_id=getattr(lead, "pool_id", None),
    )
    return lead


def _map_lead_score_to_level(score: int | None) -> str | None:
    if score is None:
        return None
    if score >= 80:
        return "A重点"
    if score >= 60:
        return "B普通"
    return "C长尾"


def _find_duplicate_customers(db: Session, tenant_id: UUID, lead: Lead) -> list[Customer]:
    q = db.query(Customer).filter(
        Customer.tenant_id == tenant_id,
        Customer.deleted_at.is_(None),
        Customer.company_name == lead.company_name,
    )
    if lead.mobile:
        q = q.filter(Customer.mobile == lead.mobile)
    return q.order_by(Customer.created_at.asc()).limit(10).all()


def convert_lead_to_customer(
    db: Session,
    ctx: TenantContext,
    lead: Lead,
    *,
    create_deal: bool = False,
    deal_title: str | None = None,
    deal_amount: float | None = None,
    deal_pipeline_id: UUID | None = None,
    deal_stage_id: UUID | None = None,
    merge_into_customer_id: UUID | None = None,
    force_create: bool = True,
) -> tuple[Customer, Contact | None, object | None, bool]:
    """返回 (customer, contact, deal|None, merged)。"""
    assert_can_mutate_lead(ctx, lead)
    if lead.status == "已转化" or lead.converted_customer_id:
        raise HTTPException(status_code=409, detail="线索已转化")

    merged = False
    customer: Customer | None = None
    if merge_into_customer_id is not None:
        customer = get_customer_for_convert(db, ctx.tenant_id, merge_into_customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="合并目标客户不存在")
        merged = True
    elif not force_create:
        dups = _find_duplicate_customers(db, ctx.tenant_id, lead)
        if dups:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "发现疑似重复客户，请选择合并或强制新建",
                    "duplicate_candidates": [str(c.id) for c in dups],
                },
            )

    if customer is None:
        extra = dict(lead.extra_data or {})
        level = _map_lead_score_to_level(lead.lead_score)
        if level:
            extra["customer_level"] = level
        customer = Customer(
            tenant_id=ctx.tenant_id,
            customer_number=generate_number(db, ctx.tenant_id, "customer"),
            company_name=lead.company_name,
            mobile=lead.mobile,
            phone=lead.phone,
            email=lead.email,
            status="潜在",
            source=_normalize_crm_source(lead.source),
            converted_lead_score=lead.lead_score,
            owner_user_id=lead.owner_user_id or ctx.user.id,
            territory_id=lead.territory_id,
            manager_user_id=getattr(lead, "manager_user_id", None),
            campaign_id=lead.campaign_id,
            converted_from_lead_id=lead.id,
            remark=lead.remark,
            extra_data=extra,
            created_by_user_id=ctx.user.id,
        )
        db.add(customer)
        db.flush()
    else:
        # 合并：补齐来源等信息（不覆盖已有非空值）
        if not customer.source and _normalize_crm_source(lead.source):
            customer.source = _normalize_crm_source(lead.source)
        if customer.converted_lead_score is None and lead.lead_score is not None:
            customer.converted_lead_score = lead.lead_score
        if not customer.converted_from_lead_id:
            customer.converted_from_lead_id = lead.id
        level = _map_lead_score_to_level(lead.lead_score)
        if level:
            extra = dict(customer.extra_data or {})
            extra.setdefault("customer_level", level)
            customer.extra_data = extra

    contact = None
    if lead.contact_name:
        contact = Contact(
            tenant_id=ctx.tenant_id,
            customer_id=customer.id,
            name=lead.contact_name,
            mobile=lead.mobile,
            phone=lead.phone,
            email=lead.email,
            title=lead.title,
            department=lead.department,
            is_primary=not merged,
            extra_data={},
        )
        db.add(contact)
        db.flush()

    if customer.owner_user_id is None or not can_view_customer(
        ctx,
        db,
        customer.owner_user_id,
        customer.territory_id,
        created_by_user_id=customer.created_by_user_id,
        manager_user_id=getattr(customer, "manager_user_id", None),
    ):
        customer.owner_user_id = ctx.user.id

    deal = None
    if create_deal:
        from app.schemas.crm_deals import DealCreate
        from app.services.crm.bant_service import deal_suggestions_from_bant, latest_evaluation
        from app.services.crm.deal_service import create_deal as create_deal_svc

        bant = latest_evaluation(db, ctx.tenant_id, lead.id)
        suggestions = deal_suggestions_from_bant(bant)
        amount = deal_amount if deal_amount is not None else suggestions.get("amount", 0)
        close_date = suggestions.get("expected_close_date")
        if close_date is not None and not isinstance(close_date, datetime):
            close_date = datetime.combine(close_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        try:
            deal_payload = DealCreate(
                title=deal_title or f"{lead.company_name}合作",
                customer_id=customer.id,
                contact_id=contact.id if contact else None,
                amount=float(amount or 0),
                source=_normalize_crm_source(lead.source),
                pipeline_id=deal_pipeline_id,
                stage_id=deal_stage_id,
                expected_close_date=close_date,
                description=suggestions.get("description"),
                contact_role=suggestions.get("contact_role"),
            )
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=f"创建商机参数无效: {exc.errors()}") from exc
        deal = create_deal_svc(
            db,
            ctx,
            deal_payload,
            commit=False,
        )

    lead.status = "已转化"
    lead.converted_customer_id = customer.id
    _copy_lead_activities_to_customer(db, ctx, lead, customer)
    db.commit()
    db.refresh(customer)
    if contact:
        db.refresh(contact)
    if deal is not None:
        db.refresh(deal)
    db.refresh(lead)
    return customer, contact, deal, merged


def get_customer_for_convert(db: Session, tenant_id: UUID, customer_id: UUID) -> Customer | None:
    return (
        db.query(Customer)
        .filter(
            uuid_eq(Customer.id, customer_id),
            Customer.tenant_id == tenant_id,
            Customer.deleted_at.is_(None),
        )
        .first()
    )


def _copy_lead_activities_to_customer(db: Session, ctx: TenantContext, lead: Lead, customer: Customer) -> None:
    activities = db.query(CrmActivity).filter(CrmActivity.lead_id == lead.id).order_by(CrmActivity.created_at).all()
    for act in activities:
        created_by = act.created_by_user_id or ctx.user.id
        db.add(
            CrmActivity(
                tenant_id=ctx.tenant_id,
                customer_id=customer.id,
                activity_type=act.activity_type or "other",
                subject=act.subject,
                content=act.content or "",
                created_by_user_id=created_by,
            )
        )
    db.flush()
