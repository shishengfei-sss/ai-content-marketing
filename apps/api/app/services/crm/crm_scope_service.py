"""CRM 数据可见范围（list_own / list_team / list_territory / list_all 并集）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.dependencies import TenantContext
from app.models.crm import Customer, CrmTask, Lead, MarketingCampaign
from app.services.crm.sales_org_service import get_accessible_territory_ids, get_subordinate_user_ids


def _perm_set(ctx: TenantContext) -> set[str]:
    return {p.permission_code for p in ctx.membership.role.permissions}


def has_lead_list_permission(ctx: TenantContext) -> bool:
    perms = _perm_set(ctx)
    return bool(
        perms.intersection(
            {
                "crm.lead.list_own",
                "crm.lead.list_team",
                "crm.lead.list_territory",
                "crm.lead.list_all",
            }
        )
    )


def has_customer_list_permission(ctx: TenantContext) -> bool:
    perms = _perm_set(ctx)
    return bool(
        perms.intersection(
            {
                "crm.customer.list_own",
                "crm.customer.list_team",
                "crm.customer.list_territory",
                "crm.customer.list_all",
            }
        )
    )


def _lead_visibility_filter(db: Session, ctx: TenantContext, perms: set[str]):
    if "crm.lead.list_all" in perms:
        return None
    if not perms.intersection({"crm.lead.list_own", "crm.lead.list_team", "crm.lead.list_territory"}):
        return Lead.id.is_(None)
    parts = [Lead.owner_user_id == ctx.user.id]
    if "crm.lead.list_team" in perms:
        subordinate_ids = get_subordinate_user_ids(db, ctx.tenant_id, ctx.membership.id)
        if subordinate_ids:
            parts.append(Lead.owner_user_id.in_(subordinate_ids))
    if "crm.lead.list_territory" in perms:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_ids:
            parts.append(Lead.territory_id.in_(territory_ids))
    return or_(*parts)


def apply_lead_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    perms = _perm_set(ctx)
    clause = _lead_visibility_filter(db, ctx, perms)
    if clause is None:
        return query
    return query.filter(clause)


def _customer_visibility_filter(db: Session, ctx: TenantContext, perms: set[str]):
    if "crm.customer.list_all" in perms:
        return None
    if not perms.intersection({"crm.customer.list_own", "crm.customer.list_team", "crm.customer.list_territory"}):
        return Customer.id.is_(None)
    parts = [Customer.owner_user_id == ctx.user.id]
    if "crm.customer.list_team" in perms:
        subordinate_ids = get_subordinate_user_ids(db, ctx.tenant_id, ctx.membership.id)
        if subordinate_ids:
            parts.append(Customer.owner_user_id.in_(subordinate_ids))
    if "crm.customer.list_territory" in perms:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_ids:
            parts.append(Customer.territory_id.in_(territory_ids))
    return or_(*parts)


def apply_customer_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    perms = _perm_set(ctx)
    clause = _customer_visibility_filter(db, ctx, perms)
    if clause is None:
        return query
    return query.filter(clause)


def can_view_lead(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID,
    territory_id: UUID | None = None,
) -> bool:
    perms = _perm_set(ctx)
    if "crm.lead.list_all" in perms:
        return True
    if owner_user_id == ctx.user.id and perms.intersection(
        {"crm.lead.list_own", "crm.lead.list_team", "crm.lead.list_territory"}
    ):
        return True
    if "crm.lead.list_team" in perms:
        subordinate_ids = get_subordinate_user_ids(db, ctx.tenant_id, ctx.membership.id)
        if owner_user_id in subordinate_ids:
            return True
    if "crm.lead.list_territory" in perms and territory_id:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_id in territory_ids:
            return True
    return False


def can_view_customer(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID,
    territory_id: UUID | None = None,
) -> bool:
    perms = _perm_set(ctx)
    if "crm.customer.list_all" in perms:
        return True
    if owner_user_id == ctx.user.id and perms.intersection(
        {"crm.customer.list_own", "crm.customer.list_team", "crm.customer.list_territory"}
    ):
        return True
    if "crm.customer.list_team" in perms:
        subordinate_ids = get_subordinate_user_ids(db, ctx.tenant_id, ctx.membership.id)
        if owner_user_id in subordinate_ids:
            return True
    if "crm.customer.list_territory" in perms and territory_id:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_id in territory_ids:
            return True
    return False


def assert_can_view_lead(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID,
    territory_id: UUID | None = None,
) -> None:
    if not can_view_lead(ctx, db, owner_user_id, territory_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该线索")


def assert_can_view_customer(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID,
    territory_id: UUID | None = None,
) -> None:
    if not can_view_customer(ctx, db, owner_user_id, territory_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该客户")


def has_task_list_permission(ctx: TenantContext) -> bool:
    perms = _perm_set(ctx)
    return bool(
        perms.intersection(
            {
                "crm.task.list_own",
                "crm.task.list_team",
                "crm.task.list_territory",
                "crm.task.list_all",
            }
        )
    )


def _task_visibility_filter(db: Session, ctx: TenantContext, perms: set[str]):
    if "crm.task.list_all" in perms:
        return None
    if not perms.intersection({"crm.task.list_own", "crm.task.list_team", "crm.task.list_territory"}):
        return CrmTask.id.is_(None)
    parts = [
        CrmTask.assignee_user_id == ctx.user.id,
        CrmTask.owner_user_id == ctx.user.id,
    ]
    if "crm.task.list_team" in perms:
        subordinate_ids = get_subordinate_user_ids(db, ctx.tenant_id, ctx.membership.id)
        if subordinate_ids:
            parts.append(CrmTask.assignee_user_id.in_(subordinate_ids))
            parts.append(CrmTask.owner_user_id.in_(subordinate_ids))
    if "crm.task.list_territory" in perms:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_ids:
            parts.append(CrmTask.territory_id.in_(territory_ids))
    return or_(*parts)


def apply_task_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    perms = _perm_set(ctx)
    clause = _task_visibility_filter(db, ctx, perms)
    if clause is None:
        return query
    return query.filter(clause)


def can_view_task(
    ctx: TenantContext,
    db: Session,
    assignee_user_id: UUID,
    owner_user_id: UUID,
    territory_id: UUID | None = None,
) -> bool:
    perms = _perm_set(ctx)
    if "crm.task.list_all" in perms:
        return True
    if assignee_user_id == ctx.user.id or owner_user_id == ctx.user.id:
        if perms.intersection({"crm.task.list_own", "crm.task.list_team", "crm.task.list_territory"}):
            return True
    if "crm.task.list_team" in perms:
        subordinate_ids = get_subordinate_user_ids(db, ctx.tenant_id, ctx.membership.id)
        if assignee_user_id in subordinate_ids or owner_user_id in subordinate_ids:
            return True
    if "crm.task.list_territory" in perms and territory_id:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_id in territory_ids:
            return True
    return False


def assert_can_view_task(ctx: TenantContext, db: Session, task: CrmTask) -> None:
    if not can_view_task(ctx, db, task.assignee_user_id, task.owner_user_id, task.territory_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该任务")


def has_campaign_list_permission(ctx: TenantContext) -> bool:
    perms = _perm_set(ctx)
    return bool(
        perms.intersection(
            {
                "crm.campaign.list_own",
                "crm.campaign.list_team",
                "crm.campaign.list_territory",
                "crm.campaign.list_all",
            }
        )
    )


def _campaign_visibility_filter(db: Session, ctx: TenantContext, perms: set[str]):
    if "crm.campaign.list_all" in perms:
        return None
    if not perms.intersection(
        {"crm.campaign.list_own", "crm.campaign.list_team", "crm.campaign.list_territory"}
    ):
        return MarketingCampaign.id.is_(None)
    parts = [MarketingCampaign.owner_user_id == ctx.user.id]
    if "crm.campaign.list_team" in perms:
        subordinate_ids = get_subordinate_user_ids(db, ctx.tenant_id, ctx.membership.id)
        if subordinate_ids:
            parts.append(MarketingCampaign.owner_user_id.in_(subordinate_ids))
    if "crm.campaign.list_territory" in perms:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_ids:
            parts.append(MarketingCampaign.territory_id.in_(territory_ids))
    return or_(*parts)


def apply_campaign_list_scope(query: Query, ctx: TenantContext, db: Session) -> Query:
    perms = _perm_set(ctx)
    clause = _campaign_visibility_filter(db, ctx, perms)
    if clause is None:
        return query
    return query.filter(clause)


def can_view_campaign(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID,
    territory_id: UUID | None = None,
) -> bool:
    perms = _perm_set(ctx)
    if "crm.campaign.list_all" in perms:
        return True
    if owner_user_id == ctx.user.id and perms.intersection(
        {"crm.campaign.list_own", "crm.campaign.list_team", "crm.campaign.list_territory", "crm.campaign.view"}
    ):
        return True
    if "crm.campaign.list_team" in perms:
        subordinate_ids = get_subordinate_user_ids(db, ctx.tenant_id, ctx.membership.id)
        if owner_user_id in subordinate_ids:
            return True
    if "crm.campaign.list_territory" in perms and territory_id:
        territory_ids = get_accessible_territory_ids(db, ctx.tenant_id, ctx.membership.id)
        if territory_id in territory_ids:
            return True
    return False


def assert_can_view_campaign(
    ctx: TenantContext,
    db: Session,
    owner_user_id: UUID,
    territory_id: UUID | None = None,
) -> None:
    if not can_view_campaign(ctx, db, owner_user_id, territory_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该活动")
